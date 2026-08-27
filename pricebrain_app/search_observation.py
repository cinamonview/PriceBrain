"""Bounded multi-query Search Batch observation — V2 Phase 7.

Orchestrates repeated dry-run search batches across a fixed query list, reusing
``run_search_batch`` and shared external-id deduplication. No new persistence layer.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from google.cloud.firestore_v1 import Client as FirestoreClient

from pricebrain_app.crawler.types import RawProductData
from pricebrain_app.pipeline.collision_review import (
    CollisionClass,
    CollisionGroupReport,
    review_canonical_collisions,
)
from pricebrain_app.pipeline.persist_boundary import (
    PersistBoundaryState,
    blocked_canonical_ids_from_state,
    review_reason_for_canonical,
)
from pricebrain_app.repository.persist_service import finalize_boundary_state
from pricebrain_app.search_batch import (
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_SEARCH_PAGES,
    DEFAULT_REQUEST_INTERVAL_SECONDS,
    SearchBatchSummary,
    SearchItemResult,
    SearchItemStatus,
    apply_persist_boundary_outcomes,
    run_search_batch,
)

# Fixed Phase 3~6 bounded query set — do not expand in Phase 7.
PHASE7_BOUNDED_QUERIES: tuple[str, ...] = (
    "RTX 4070",
    "RTX 5070",
    "RTX 5080",
    "RX 9070",
    "그래픽카드",
    "지포스 RTX",
)

_PRODUCTION_QUOTA_MARKERS: tuple[str, ...] = (
    "ResourceExhausted",
    "Quota exceeded",
    "429",
)


def is_production_quota_failure(item: SearchItemResult) -> bool:
    """True when a FAILED item is caused by Firestore quota, not pipeline logic."""
    if item.status is not SearchItemStatus.FAILED:
        return False
    haystack = f"{item.error_category or ''} {item.message}"
    return any(marker in haystack for marker in _PRODUCTION_QUOTA_MARKERS)


@dataclass(frozen=True)
class QueryObservation:
    query: str
    summary: SearchBatchSummary
    results: tuple[SearchItemResult, ...]
    quota_failures: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload = dict(self.summary.to_dict())
        payload["quota_failures"] = self.quota_failures
        return payload


@dataclass(frozen=True)
class ObservationClassification:
    known_gpu: int = 0
    unknown_gpu: int = 0
    gpu_accessory: int = 0
    prebuilt_pc: int = 0
    laptop: int = 0
    brandless: int = 0
    deferred_partner: int = 0
    other_validation_failed: int = 0
    failed_non_quota: int = 0
    quota_failures: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "known_gpu": self.known_gpu,
            "unknown_gpu": self.unknown_gpu,
            "gpu_accessory": self.gpu_accessory,
            "prebuilt_pc": self.prebuilt_pc,
            "laptop": self.laptop,
            "brandless": self.brandless,
            "deferred_partner": self.deferred_partner,
            "other_validation_failed": self.other_validation_failed,
            "failed_non_quota": self.failed_non_quota,
            "quota_failures": self.quota_failures,
        }


@dataclass(frozen=True)
class IdentityObservation:
    unique_external_ids: int
    unique_canonical_product_ids: int
    canonical_id_collisions: int
    listing_id_by_external: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unique_external_ids": self.unique_external_ids,
            "unique_canonical_product_ids": self.unique_canonical_product_ids,
            "canonical_id_collisions": self.canonical_id_collisions,
            "listing_id_by_external": dict(self.listing_id_by_external),
        }


@dataclass(frozen=True)
class CollisionReviewObservation:
    collision_groups: tuple[CollisionGroupReport, ...]
    review_required_count: int = 0
    c2_count: int = 0
    c3_count: int = 0
    c4_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "collision_groups": [group.to_dict() for group in self.collision_groups],
            "review_required_count": self.review_required_count,
            "c2_count": self.c2_count,
            "c3_count": self.c3_count,
            "c4_count": self.c4_count,
        }


@dataclass(frozen=True)
class MultiQueryObservationReport:
    dry_run: bool
    queries: tuple[QueryObservation, ...]
    aggregate: SearchBatchSummary
    classification: ObservationClassification
    identity: IdentityObservation
    collision_review: CollisionReviewObservation
    production_reads: int | None = None
    production_writes: int | None = None
    blocked_writes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "queries": [q.to_dict() for q in self.queries],
            "aggregate": self.aggregate.to_dict(),
            "classification": self.classification.to_dict(),
            "identity": self.identity.to_dict(),
            "collision_review": self.collision_review.to_dict(),
            "production_reads": self.production_reads,
            "production_writes": self.production_writes,
            "blocked_writes": self.blocked_writes,
        }


def classify_observation_items(
    items: Iterable[SearchItemResult],
) -> ObservationClassification:
    """Report-only breakdown — does not alter Search Batch statuses."""
    known = unknown = accessory = prebuilt = laptop = 0
    brandless = deferred = other_validation = 0
    failed_non_quota = quota = 0

    for item in items:
        if is_production_quota_failure(item):
            quota += 1
            continue
        if item.status in (
            SearchItemStatus.PERSIST_CANDIDATE,
            SearchItemStatus.PERSISTED,
        ):
            known += 1
            continue
        if item.status is SearchItemStatus.QUARANTINED:
            unknown += 1
            continue
        if item.status is SearchItemStatus.IRRELEVANT:
            category = (item.error_category or "").upper()
            if category == "GPU_ACCESSORY":
                accessory += 1
            elif category == "PREBUILT_PC":
                prebuilt += 1
            elif category == "LAPTOP":
                laptop += 1
            continue
        if item.status is SearchItemStatus.VALIDATION_FAILED:
            title = (item.product_name or "").lower()
            if any(token in title for token in ("emtek", "이엠텍", "abovetop", "yeston")):
                deferred += 1
            elif item.board_partner_id:
                other_validation += 1
            else:
                brandless += 1
            continue
        if item.status is SearchItemStatus.FAILED:
            failed_non_quota += 1

    return ObservationClassification(
        known_gpu=known,
        unknown_gpu=unknown,
        gpu_accessory=accessory,
        prebuilt_pc=prebuilt,
        laptop=laptop,
        brandless=brandless,
        deferred_partner=deferred,
        other_validation_failed=other_validation,
        failed_non_quota=failed_non_quota,
        quota_failures=quota,
    )


def observe_identity(items: Iterable[SearchItemResult]) -> IdentityObservation:
    external_ids: set[str] = set()
    canonical_by_external: dict[str, str] = {}
    listing_by_external: dict[str, str] = {}
    canonical_counts: dict[str, int] = {}

    for item in items:
        ext = item.external_product_id
        if not ext:
            continue
        external_ids.add(ext)
        if item.canonical_product_id:
            canonical_by_external.setdefault(ext, item.canonical_product_id)
            canonical_counts[item.canonical_product_id] = (
                canonical_counts.get(item.canonical_product_id, 0) + 1
            )
        if item.listing_id:
            listing_by_external.setdefault(ext, item.listing_id)

    collisions = sum(1 for count in canonical_counts.values() if count > 1)
    return IdentityObservation(
        unique_external_ids=len(external_ids),
        unique_canonical_product_ids=len(canonical_counts),
        canonical_id_collisions=collisions,
        listing_id_by_external=listing_by_external,
    )


def observe_collision_review(
    items: Iterable[SearchItemResult],
    *,
    mpn_by_external: Mapping[str, str | None] | None = None,
) -> CollisionReviewObservation:
    """Read-only review of canonical collision groups."""
    groups = review_canonical_collisions(items, mpn_by_external=mpn_by_external)
    c2 = sum(1 for group in groups if group.collision_class is CollisionClass.C2_NORMAL_LISTING)
    c3 = sum(1 for group in groups if group.collision_class is CollisionClass.C3_VARIANT_COLLISION)
    c4 = sum(1 for group in groups if group.collision_class is CollisionClass.C4_HIGH_RISK)
    review_required = sum(1 for group in groups if group.review_required)
    return CollisionReviewObservation(
        collision_groups=groups,
        review_required_count=review_required,
        c2_count=c2,
        c3_count=c3,
        c4_count=c4,
    )


def reconcile_persist_boundary_items(
    items: Iterable[SearchItemResult],
    state: PersistBoundaryState,
) -> tuple[SearchItemResult, ...]:
    """Downgrade prior persist candidates implicated in a blocked collision group."""
    blocked = blocked_canonical_ids_from_state(state)
    if not blocked:
        return tuple(items)

    reconciled: list[SearchItemResult] = []
    for item in items:
        if (
            item.status is SearchItemStatus.PERSIST_CANDIDATE
            and item.canonical_product_id in blocked
        ):
            reason = review_reason_for_canonical(
                item.canonical_product_id,
                state.all_members(),
                mpn_by_external=state.mpn_by_external,
            )
            reconciled.append(
                SearchItemResult(
                    status=SearchItemStatus.IDENTITY_REVIEW_BLOCKED,
                    mall_id=item.mall_id,
                    query=item.query,
                    page=item.page,
                    rank=item.rank,
                    external_product_id=item.external_product_id,
                    product_name=item.product_name,
                    product_url=item.product_url,
                    gpu_model_id=item.gpu_model_id,
                    board_partner_id=item.board_partner_id,
                    canonical_product_id=item.canonical_product_id,
                    listing_id=None,
                    error_category="identity_review",
                    message="persist blocked by collision review gate",
                    review_required=True,
                    review_reason=reason,
                    observed_at=item.observed_at,
                )
            )
            continue
        reconciled.append(item)
    return tuple(reconciled)


def aggregate_query_summaries(
    observations: Sequence[QueryObservation],
    *,
    dry_run: bool,
    mall_id: str = "elevenst",
) -> SearchBatchSummary:
    unknown_models: dict[str, int] = {}
    totals = {
        "search_api_calls": 0,
        "collected": 0,
        "duplicates_skipped": 0,
        "processed": 0,
        "persisted": 0,
        "persist_candidates": 0,
        "identity_review_blocked": 0,
        "quarantined": 0,
        "validation_failed": 0,
        "irrelevant": 0,
        "failed": 0,
    }
    for obs in observations:
        summary = obs.summary
        totals["search_api_calls"] += summary.search_api_calls
        totals["collected"] += summary.collected
        totals["duplicates_skipped"] += summary.duplicates_skipped
        totals["processed"] += summary.processed
        totals["persisted"] += summary.persisted
        totals["persist_candidates"] += summary.persist_candidates
        totals["identity_review_blocked"] += summary.identity_review_blocked
        totals["quarantined"] += summary.quarantined
        totals["validation_failed"] += summary.validation_failed
        totals["irrelevant"] += summary.irrelevant
        totals["failed"] += summary.failed
        for slug, count in summary.unknown_models.items():
            unknown_models[slug] = unknown_models.get(slug, 0) + count

    return SearchBatchSummary(
        query="(multi-query aggregate)",
        mall_id=mall_id,
        dry_run=dry_run,
        requested=DEFAULT_SEARCH_LIMIT,
        pages=DEFAULT_SEARCH_PAGES,
        unknown_models=unknown_models,
        **totals,
    )


def run_multi_query_observation(
    *,
    queries: Sequence[str],
    search_page_for_query: Callable[[str, int], Iterable[RawProductData]],
    db: FirestoreClient,
    mall_id: str = "elevenst",
    limit: int | None = DEFAULT_SEARCH_LIMIT,
    pages: int | None = DEFAULT_SEARCH_PAGES,
    dry_run: bool = True,
    request_interval_seconds: float = DEFAULT_REQUEST_INTERVAL_SECONDS,
    sleep_func: Callable[[float], None] | None = None,
) -> MultiQueryObservationReport:
    """Run bounded dry-run (default) batches for each query with shared dedup."""
    if not queries:
        raise ValueError("at least one query is required")

    seen_external_ids: set[str] = set()
    boundary_state = PersistBoundaryState()
    observations: list[QueryObservation] = []
    all_items: list[SearchItemResult] = []

    for query in queries:
        cleaned = query.strip()
        if not cleaned:
            raise ValueError("empty query is not allowed")

        def search_page(q: str, page: int, *, _q: str = cleaned) -> Iterable[RawProductData]:
            if q != _q:
                return []
            return search_page_for_query(_q, page)

        results, summary = run_search_batch(
            query=cleaned,
            search_page=search_page,
            db=db,
            mall_id=mall_id,
            limit=limit,
            pages=pages,
            dry_run=dry_run,
            seen_external_ids=seen_external_ids,
            persist_boundary_state=boundary_state,
            defer_boundary_finalize=True,
            request_interval_seconds=request_interval_seconds,
            sleep_func=sleep_func or __import__("time").sleep,
        )
        quota_failures = sum(1 for item in results if is_production_quota_failure(item))
        observations.append(
            QueryObservation(
                query=cleaned,
                summary=summary,
                results=tuple(results),
                quota_failures=quota_failures,
            )
        )
        all_items.extend(results)

    if boundary_state.deferred:
        outcomes = finalize_boundary_state(boundary_state, db=db, dry_run=dry_run)
        all_items = apply_persist_boundary_outcomes(all_items, outcomes)
        boundary_state.deferred.clear()
        observations = [
            QueryObservation(
                query=obs.query,
                summary=obs.summary,
                results=tuple(
                    apply_persist_boundary_outcomes(list(obs.results), outcomes)
                ),
                quota_failures=obs.quota_failures,
            )
            for obs in observations
        ]

    all_items = list(reconcile_persist_boundary_items(all_items, boundary_state))
    observations = [
        QueryObservation(
            query=obs.query,
            summary=obs.summary,
            results=tuple(
                reconcile_persist_boundary_items(obs.results, boundary_state)
            ),
            quota_failures=obs.quota_failures,
        )
        for obs in observations
    ]

    aggregate = aggregate_query_summaries(observations, dry_run=dry_run, mall_id=mall_id)
    return MultiQueryObservationReport(
        dry_run=dry_run,
        queries=tuple(observations),
        aggregate=aggregate,
        classification=classify_observation_items(all_items),
        identity=observe_identity(all_items),
        collision_review=observe_collision_review(all_items),
    )


def fixture_map_for_queries(
    fixtures: Mapping[str, Iterable[RawProductData]],
) -> Callable[[str, int], Iterable[RawProductData]]:
    """Build a search_page resolver from a query→items map (page 1 only)."""

    def search_page_for_query(query: str, page: int) -> Iterable[RawProductData]:
        if page != 1:
            return []
        return fixtures.get(query, ())

    return search_page_for_query
