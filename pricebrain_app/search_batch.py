"""Bounded search batch — classify search results without losing or aborting.

Lives beside runner.py because it spans layers: docs/07 forbids the crawler package
from importing pipeline/repository/Firestore, so cross-layer orchestration belongs here.

Reuses the existing path end to end: mall search adapter → pipeline (clean →
normalize → parse_gpu → match → validate) → repository persist, with Phase 2.5's
unknown-GPU quarantine. Nothing here re-implements parsing, validation or persistence.

Two hard guarantees, both regression guards for Phase 2.5 findings:
  * one bad item never aborts the batch (Phase 2.5 P2)
  * an unknown GPU model goes to pending_gpu_models, never nowhere (Phase 2.5 P1)
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from google.cloud.firestore_v1 import Client as FirestoreClient

from pricebrain_app.crawler.logging_utils import get_crawler_logger, safe_url_for_log
from pricebrain_app.crawler.types import RawProductData
from pricebrain_app.pipeline.exceptions import (
    GpuProductFilteredError,
    PipelineValidationError,
)
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.pipeline.utils import normalize_mall_id
from pricebrain_app.pipeline.persist_boundary import (
    PersistBoundaryState,
)
from pricebrain_app.repository.exceptions import (
    RepositoryValidationError,
    UnknownGpuModelError,
)
from pricebrain_app.repository.gpu_repository import GpuRepository
from pricebrain_app.repository.operational_service import (
    quarantine_unknown_gpu_model,
)
from pricebrain_app.repository.persist_service import (
    PersistDecision,
    defer_validated_product,
    finalize_boundary_state,
)
from pricebrain_app.repository.validation import validate_for_persist

logger = get_crawler_logger()

DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 50
DEFAULT_SEARCH_PAGES = 1
MAX_SEARCH_PAGES = 3
DEFAULT_REQUEST_INTERVAL_SECONDS = 1.5


class SearchItemStatus(StrEnum):
    """Outcome of one search result.

    Distinct from CrawlerStatus, which describes transport outcomes (HTTP/timeout).
    These describe what the ingest path decided to do with an item.
    """

    PERSISTED = "PERSISTED"
    PERSIST_CANDIDATE = "PERSIST_CANDIDATE"  # dry-run counterpart of PERSISTED
    IDENTITY_REVIEW_BLOCKED = "IDENTITY_REVIEW_BLOCKED"
    QUARANTINED = "QUARANTINED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    IRRELEVANT = "IRRELEVANT"
    FAILED = "FAILED"


@dataclass(frozen=True)
class SearchItemResult:
    """Per-item observation record — no raw HTML/JSON retained."""

    status: SearchItemStatus
    mall_id: str
    query: str
    page: int
    rank: int
    external_product_id: str | None = None
    product_name: str = ""
    product_url: str | None = None
    gpu_model_id: str | None = None
    board_partner_id: str | None = None
    canonical_product_id: str | None = None
    listing_id: str | None = None
    error_category: str | None = None
    message: str = ""
    review_required: bool = False
    review_reason: str | None = None
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "mall_id": self.mall_id,
            "query": self.query,
            "page": self.page,
            "rank": self.rank,
            "external_product_id": self.external_product_id,
            "product_name": self.product_name,
            "product_url": self.product_url,
            "gpu_model_id": self.gpu_model_id,
            "board_partner_id": self.board_partner_id,
            "canonical_product_id": self.canonical_product_id,
            "listing_id": self.listing_id,
            "error_category": self.error_category,
            "message": self.message,
            "review_required": self.review_required,
            "review_reason": self.review_reason,
            "observed_at": self.observed_at.isoformat(),
        }


@dataclass(frozen=True)
class SearchBatchSummary:
    query: str
    mall_id: str
    dry_run: bool
    requested: int
    pages: int
    search_api_calls: int = 0
    collected: int = 0
    duplicates_skipped: int = 0
    processed: int = 0
    persisted: int = 0
    persist_candidates: int = 0
    identity_review_blocked: int = 0
    quarantined: int = 0
    validation_failed: int = 0
    irrelevant: int = 0
    failed: int = 0
    unknown_models: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "mall": self.mall_id,
            "dry_run": self.dry_run,
            "requested": self.requested,
            "pages": self.pages,
            "search_api_calls": self.search_api_calls,
            "collected": self.collected,
            "duplicates_skipped": self.duplicates_skipped,
            "processed": self.processed,
            "persisted": self.persisted,
            "persist_candidates": self.persist_candidates,
            "identity_review_blocked": self.identity_review_blocked,
            "quarantined": self.quarantined,
            "validation_failed": self.validation_failed,
            "irrelevant": self.irrelevant,
            "failed": self.failed,
            "unknown_models": dict(self.unknown_models),
        }

    def format_summary(self) -> str:
        mode = "dry-run" if self.dry_run else "live"
        lines = [
            f"Search batch summary ({mode})",
            "",
            f"query: {self.query}",
            f"mall: {self.mall_id}",
            f"pages: {self.pages}",
            f"requested: {self.requested}",
            f"search_api_calls: {self.search_api_calls}",
            f"collected: {self.collected}",
            f"duplicates_skipped: {self.duplicates_skipped}",
            f"processed: {self.processed}",
            f"persisted: {self.persisted}",
            f"persist_candidates: {self.persist_candidates}",
            f"identity_review_blocked: {self.identity_review_blocked}",
            f"quarantined: {self.quarantined}",
            f"validation_failed: {self.validation_failed}",
            f"irrelevant: {self.irrelevant}",
            f"failed: {self.failed}",
        ]
        if self.unknown_models:
            lines.append("")
            lines.append("unknown GPU models:")
            for slug, count in sorted(
                self.unknown_models.items(), key=lambda kv: (-kv[1], kv[0])
            ):
                lines.append(f"  {slug:20} {count}")
        return "\n".join(lines)


def resolve_search_limit(limit: int | None) -> int:
    """Clamp the requested limit to the hard cap; never unbounded."""
    if limit is None:
        return DEFAULT_SEARCH_LIMIT
    if limit < 1:
        raise ValueError(f"search limit must be >= 1: {limit}")
    return min(limit, MAX_SEARCH_LIMIT)


def resolve_search_pages(pages: int | None) -> int:
    if pages is None:
        return DEFAULT_SEARCH_PAGES
    if pages < 1:
        raise ValueError(f"search pages must be >= 1: {pages}")
    return min(pages, MAX_SEARCH_PAGES)


def _classify_dry_run(db: FirestoreClient, validated: dict[str, Any]) -> tuple[
    SearchItemStatus, str | None, str
]:
    """Decide the outcome without writing anything.

    Mirrors save_validated_product's order using the same pure validator and the
    same read-only master lookups, so dry-run and live agree.
    """
    try:
        validate_for_persist(validated)
    except RepositoryValidationError as exc:
        return SearchItemStatus.VALIDATION_FAILED, exc.field, str(exc)

    gpu_repo = GpuRepository(db)
    partner_id = str(validated["board_partner_id"])
    if gpu_repo.get_partner(partner_id) is None:
        return (
            SearchItemStatus.VALIDATION_FAILED,
            "board_partner_id",
            f"board_partner_id not found in GPU master: {partner_id}",
        )

    model_id = str(validated["gpu_model_id"])
    if gpu_repo.get_model(model_id) is None:
        return (
            SearchItemStatus.QUARANTINED,
            "gpu_model_id",
            f"gpu_model_id not found in GPU master: {model_id}",
        )

    return SearchItemStatus.PERSIST_CANDIDATE, None, "persist candidate"


def _process_item(
    raw: RawProductData,
    *,
    db: FirestoreClient | None,
    query: str,
    mall_id: str,
    page: int,
    rank: int,
    dry_run: bool = True,
) -> tuple[SearchItemResult, dict[str, Any] | None]:
    """Classify one search result. Persist candidates finalize after collision gate."""
    base: dict[str, Any] = {
        "mall_id": mall_id,
        "query": query,
        "page": page,
        "rank": rank,
        "external_product_id": str(raw.get("product_id") or "") or None,
        "product_name": str(raw.get("product_name") or ""),
        "product_url": str(raw.get("product_url") or "") or None,
    }

    if db is None:
        raise ValueError("db is required to classify search results")

    validated: dict[str, Any] = {}
    try:
        validated = dict(run_pipeline(dict(raw)))
        base["gpu_model_id"] = validated.get("gpu_model_id")
        base["board_partner_id"] = validated.get("board_partner_id")
        base["canonical_product_id"] = validated.get("canonical_product_id")

        status, error_category, message = _classify_dry_run(db, validated)
        if status is SearchItemStatus.PERSIST_CANDIDATE:
            return (
                SearchItemResult(
                    status=status,
                    error_category=error_category,
                    message="pending persist boundary gate",
                    **base,
                ),
                validated,
            )
        if status is SearchItemStatus.QUARANTINED and not dry_run:
            model_id = str(validated.get("gpu_model_id") or "")
            exc = UnknownGpuModelError(message, gpu_model_id=model_id)
            quarantine_unknown_gpu_model(db, exc, validated_data=validated)
        return (
            SearchItemResult(
                status=status,
                error_category=error_category,
                message=message,
                **base,
            ),
            None,
        )
    except GpuProductFilteredError as exc:
        return (
            SearchItemResult(
                status=SearchItemStatus.IRRELEVANT,
                error_category=exc.field,
                message=str(exc),
                **base,
            ),
            None,
        )
    except PipelineValidationError as exc:
        return (
            SearchItemResult(
                status=SearchItemStatus.VALIDATION_FAILED,
                error_category=exc.field,
                message=str(exc),
                **base,
            ),
            None,
        )
    except UnknownGpuModelError as exc:
        if not dry_run:
            quarantine_unknown_gpu_model(db, exc, validated_data=validated)
        return (
            SearchItemResult(
                status=SearchItemStatus.QUARANTINED,
                error_category="gpu_model_id",
                message=str(exc),
                **base,
            ),
            None,
        )
    except RepositoryValidationError as exc:
        return (
            SearchItemResult(
                status=SearchItemStatus.VALIDATION_FAILED,
                error_category=exc.field,
                message=str(exc),
                **base,
            ),
            None,
        )
    except Exception as exc:  # noqa: BLE001 - isolate one item, keep the batch alive
        logger.exception(
            "search item failed",
            extra={
                "query": query,
                "url": safe_url_for_log(base["product_url"] or ""),
                "external_product_id": base["external_product_id"],
            },
        )
        return (
            SearchItemResult(
                status=SearchItemStatus.FAILED,
                error_category=type(exc).__name__,
                message=str(exc),
                **base,
            ),
            None,
        )


def _search_result_from_persist_outcome(
    result: SearchItemResult,
    outcome: Any,
) -> SearchItemResult:
    from pricebrain_app.repository.persist_service import PersistOutcome

    assert isinstance(outcome, PersistOutcome)
    if outcome.decision is PersistDecision.IDENTITY_REVIEW_BLOCKED:
        return SearchItemResult(
            status=SearchItemStatus.IDENTITY_REVIEW_BLOCKED,
            mall_id=result.mall_id,
            query=result.query,
            page=result.page,
            rank=result.rank,
            external_product_id=result.external_product_id,
            product_name=result.product_name,
            product_url=result.product_url,
            gpu_model_id=result.gpu_model_id,
            board_partner_id=result.board_partner_id,
            canonical_product_id=result.canonical_product_id,
            listing_id=None,
            error_category=outcome.error_category or "identity_review",
            message=outcome.message or "persist blocked by collision review gate",
            review_required=True,
            review_reason=outcome.review_reason,
            observed_at=result.observed_at,
        )
    if outcome.decision is PersistDecision.FAILED:
        return SearchItemResult(
            status=SearchItemStatus.FAILED,
            mall_id=result.mall_id,
            query=result.query,
            page=result.page,
            rank=result.rank,
            external_product_id=result.external_product_id,
            product_name=result.product_name,
            product_url=result.product_url,
            gpu_model_id=result.gpu_model_id,
            board_partner_id=result.board_partner_id,
            canonical_product_id=result.canonical_product_id,
            listing_id=None,
            error_category=outcome.error_category,
            message=outcome.message,
            observed_at=result.observed_at,
        )
    if outcome.decision is PersistDecision.PERSIST_CANDIDATE:
        return SearchItemResult(
            status=SearchItemStatus.PERSIST_CANDIDATE,
            mall_id=result.mall_id,
            query=result.query,
            page=result.page,
            rank=result.rank,
            external_product_id=result.external_product_id,
            product_name=result.product_name,
            product_url=result.product_url,
            gpu_model_id=result.gpu_model_id,
            board_partner_id=result.board_partner_id,
            canonical_product_id=result.canonical_product_id,
            listing_id=result.listing_id,
            message="persist candidate",
            observed_at=result.observed_at,
        )
    save_result = outcome.save_result or {}
    return SearchItemResult(
        status=SearchItemStatus.PERSISTED,
        mall_id=result.mall_id,
        query=result.query,
        page=result.page,
        rank=result.rank,
        external_product_id=result.external_product_id,
        product_name=result.product_name,
        product_url=result.product_url,
        gpu_model_id=result.gpu_model_id,
        board_partner_id=result.board_partner_id,
        canonical_product_id=result.canonical_product_id,
        listing_id=str(save_result.get("listing_id") or "") or None,
        message="persisted",
        observed_at=result.observed_at,
    )


def _finalize_persist_boundary(
    results: list[SearchItemResult],
    pending: list[tuple[int, dict[str, Any]]],
    *,
    db: FirestoreClient,
    dry_run: bool,
    boundary_state: PersistBoundaryState | None,
    defer_finalize: bool = False,
) -> None:
    """Apply collision review gate, then persist or block each pending candidate."""
    if not pending:
        return

    state = boundary_state if boundary_state is not None else PersistBoundaryState()
    for idx, validated in pending:
        result = results[idx]
        external_id = result.external_product_id
        if not external_id:
            continue
        defer_validated_product(
            state,
            validated,
            external_product_id=external_id,
            product_name=result.product_name,
        )

    if defer_finalize:
        return

    outcomes = finalize_boundary_state(state, db=db, dry_run=dry_run)
    outcome_by_external = {outcome.external_product_id: outcome for outcome in outcomes}
    for idx, _validated in pending:
        result = results[idx]
        external_id = result.external_product_id
        if not external_id:
            continue
        outcome = outcome_by_external.get(external_id)
        if outcome is None:
            continue
        results[idx] = _search_result_from_persist_outcome(result, outcome)

    if boundary_state is not None:
        boundary_state.deferred.clear()


def apply_persist_boundary_outcomes(
    results: Iterable[SearchItemResult],
    outcomes: list[Any],
) -> list[SearchItemResult]:
    """Update search item results from shared persist boundary finalize outcomes."""
    outcome_by_external = {
        outcome.external_product_id: outcome for outcome in outcomes
    }
    updated: list[SearchItemResult] = []
    for item in results:
        external_id = item.external_product_id
        if external_id and external_id in outcome_by_external:
            updated.append(
                _search_result_from_persist_outcome(
                    item, outcome_by_external[external_id]
                )
            )
        else:
            updated.append(item)
    return updated


def run_search_batch(
    *,
    query: str,
    search_page: Callable[[str, int], Iterable[RawProductData]],
    db: FirestoreClient | None = None,
    mall_id: str = "elevenst",
    limit: int | None = None,
    pages: int | None = None,
    dry_run: bool = True,
    seen_external_ids: set[str] | None = None,
    persist_boundary_state: PersistBoundaryState | None = None,
    defer_boundary_finalize: bool = False,
    request_interval_seconds: float = DEFAULT_REQUEST_INTERVAL_SECONDS,
    sleep_func: Callable[[float], None] = time.sleep,
) -> tuple[list[SearchItemResult], SearchBatchSummary]:
    """Run one bounded search batch.

    `search_page(query, page)` supplies raw products for a page, letting tests and
    offline fixtures drive the batch without HTTP. Page fetch failures are recorded
    and the batch continues to the next page.
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        raise ValueError("search query is required")

    effective_limit = resolve_search_limit(limit)
    effective_pages = resolve_search_pages(pages)
    canonical_mall = normalize_mall_id(mall_id) or mall_id.lower()

    results: list[SearchItemResult] = []
    pending_persist: list[tuple[int, dict[str, Any]]] = []
    seen: set[str] = seen_external_ids if seen_external_ids is not None else set()
    api_calls = 0
    collected = 0
    duplicates = 0

    for page in range(1, effective_pages + 1):
        if len(results) >= effective_limit:
            break
        if page > 1 and request_interval_seconds > 0:
            sleep_func(request_interval_seconds)

        try:
            page_items = list(search_page(cleaned_query, page))
            api_calls += 1
        except Exception as exc:  # noqa: BLE001 - a bad page must not kill the batch
            logger.exception(
                "search page failed", extra={"query": cleaned_query, "page": page}
            )
            api_calls += 1
            results.append(
                SearchItemResult(
                    status=SearchItemStatus.FAILED,
                    mall_id=canonical_mall,
                    query=cleaned_query,
                    page=page,
                    rank=-1,
                    error_category=type(exc).__name__,
                    message=str(exc),
                )
            )
            continue

        for rank, raw in enumerate(page_items):
            if len(results) >= effective_limit:
                break
            collected += 1
            try:
                external_id = str(raw.get("product_id") or "").strip()
            except Exception:  # noqa: BLE001 - unusable identity, still isolate it
                external_id = ""
            if external_id and external_id in seen:
                duplicates += 1
                continue
            if external_id:
                seen.add(external_id)
            validated: dict[str, Any] | None = None
            try:
                item_result, validated = _process_item(
                    raw,
                    db=db,
                    query=cleaned_query,
                    mall_id=canonical_mall,
                    page=page,
                    rank=rank,
                    dry_run=dry_run,
                )
            except Exception as exc:  # noqa: BLE001 - outermost per-item boundary
                logger.exception(
                    "search item unrecoverable",
                    extra={"query": cleaned_query, "page": page, "rank": rank},
                )
                validated = None
                item_result = SearchItemResult(
                    status=SearchItemStatus.FAILED,
                    mall_id=canonical_mall,
                    query=cleaned_query,
                    page=page,
                    rank=rank,
                    external_product_id=external_id or None,
                    error_category=type(exc).__name__,
                    message=str(exc),
                )
            results.append(item_result)
            if validated is not None:
                pending_persist.append((len(results) - 1, validated))

    if db is not None:
        _finalize_persist_boundary(
            results,
            pending_persist,
            db=db,
            dry_run=dry_run,
            boundary_state=persist_boundary_state,
            defer_finalize=defer_boundary_finalize,
        )

    counts: dict[SearchItemStatus, int] = {status: 0 for status in SearchItemStatus}
    unknown_models: dict[str, int] = {}
    for item in results:
        counts[item.status] += 1
        if item.status is SearchItemStatus.QUARANTINED and item.gpu_model_id:
            unknown_models[item.gpu_model_id] = unknown_models.get(item.gpu_model_id, 0) + 1

    summary = SearchBatchSummary(
        query=cleaned_query,
        mall_id=canonical_mall,
        dry_run=dry_run,
        requested=effective_limit,
        pages=effective_pages,
        search_api_calls=api_calls,
        collected=collected,
        duplicates_skipped=duplicates,
        processed=len(results),
        persisted=counts[SearchItemStatus.PERSISTED],
        persist_candidates=counts[SearchItemStatus.PERSIST_CANDIDATE],
        identity_review_blocked=counts[SearchItemStatus.IDENTITY_REVIEW_BLOCKED],
        quarantined=counts[SearchItemStatus.QUARANTINED],
        validation_failed=counts[SearchItemStatus.VALIDATION_FAILED],
        irrelevant=counts[SearchItemStatus.IRRELEVANT],
        failed=counts[SearchItemStatus.FAILED],
        unknown_models=unknown_models,
    )
    return results, summary
