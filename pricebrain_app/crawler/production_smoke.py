"""Production-like local smoke orchestration — reuses Worker/Scheduler, no duplicate crawl logic."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any, Callable

from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.crawler.client import IngestClient
from pricebrain_app.crawler.config import clear_crawler_config_cache
from pricebrain_app.crawler.logging_utils import redact_secrets, safe_url_for_log
from pricebrain_app.crawler.results import CrawlerResult, CrawlerStatus
from pricebrain_app.crawler.scheduler import CrawlerScheduler
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.targets import CRAWL_STATUS_IDLE, CrawlTarget, utc_now
from pricebrain_app.crawler.worker import CrawlerWorker, generate_worker_owner_id
from pricebrain_app.firebase.admin import get_firestore_client
from pricebrain_app.repository import constants as c

FirestoreFactory = Callable[[], Any]
WorkerFactory = Callable[[CrawlTargetRepository], CrawlerWorker]
IngestClientFactory = Callable[[], IngestClient]


class SmokeExitCode(IntEnum):
    SUCCESS = 0
    ERROR = 1
    SKIP = 2


@dataclass(frozen=True)
class SmokeConfig:
    target_id: str
    ingest: bool = False
    verify_firestore: bool = False
    verify_product: bool = False
    verify_listing: bool = False
    verify_price_history: bool = False
    json_output: bool = False
    timeout: float | None = None
    lease_seconds: int | None = None
    owner_id: str | None = None


@dataclass
class TargetSnapshot:
    target_id: str
    mall_id: str | None = None
    product_url: str | None = None
    enabled: bool | None = None
    crawl_interval_seconds: int | None = None
    crawl_status: str | None = None
    lease_owner: str | None = None
    lease_until: str | None = None
    last_status: str | None = None
    last_error_code: str | None = None
    last_crawled_at: str | None = None
    next_crawl_at: str | None = None
    last_crawled_price: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "mall_id": self.mall_id,
            "product_url": self.product_url,
            "enabled": self.enabled,
            "crawl_interval_seconds": self.crawl_interval_seconds,
            "crawl_status": self.crawl_status,
            "lease_owner": self.lease_owner,
            "lease_until": self.lease_until,
            "last_status": self.last_status,
            "last_error_code": self.last_error_code,
            "last_crawled_at": self.last_crawled_at,
            "next_crawl_at": self.next_crawl_at,
            "last_crawled_price": self.last_crawled_price,
        }


@dataclass
class SmokeOutcome:
    target_id: str
    exit_code: SmokeExitCode
    message: str = ""
    before: TargetSnapshot | None = None
    after: TargetSnapshot | None = None
    crawl_result: CrawlerResult | None = None
    ingest_attempted: bool = False
    ingest_status: str | None = None
    lease_released: bool = False
    firestore_verified: bool = False
    ingest_integrity: dict[str, Any] = field(default_factory=dict)
    product_verification: dict[str, Any] = field(default_factory=dict)
    listing_verification: dict[str, Any] = field(default_factory=dict)
    price_history_verification: dict[str, Any] = field(default_factory=dict)
    claimed: bool = False
    skipped: bool = False

    @property
    def last_status(self) -> str | None:
        if self.crawl_result is not None:
            return self.crawl_result.status.value
        if self.after is not None:
            return self.after.last_status
        return None

    @property
    def error_code(self) -> str | None:
        if self.after is not None and self.after.last_error_code:
            return self.after.last_error_code
        if self.crawl_result is not None and self.crawl_result.message in {
            "SSG_ACCESS_DENIED",
            "ACCESS_DENIED",
            "NOT_FOUND",
        }:
            return self.crawl_result.message
        return None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "mall_id": self.after.mall_id if self.after else (self.before.mall_id if self.before else None),
            "exit_code": int(self.exit_code),
            "message": self.message or None,
            "last_status": self.last_status,
            "error_code": self.error_code,
            "ingest_attempted": self.ingest_attempted,
            "ingest_status": self.ingest_status,
            "lease_released": self.lease_released,
            "firestore_verified": self.firestore_verified,
            "claimed": self.claimed,
            "skipped": self.skipped,
            "before": self.before.to_dict() if self.before else None,
            "after": self.after.to_dict() if self.after else None,
            "ingest_integrity": self.ingest_integrity or None,
            "product_verification": self.product_verification or None,
            "listing_verification": self.listing_verification or None,
            "price_history_verification": self.price_history_verification or None,
        }


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=utc_now().tzinfo)
    return value.isoformat()


def snapshot_target(target: CrawlTarget | None, *, target_id: str) -> TargetSnapshot | None:
    if target is None:
        return None
    return TargetSnapshot(
        target_id=target.target_id or target_id,
        mall_id=target.mall_id,
        product_url=safe_url_for_log(target.product_url),
        enabled=target.enabled,
        crawl_interval_seconds=target.crawl_interval_seconds,
        crawl_status=target.crawl_status,
        lease_owner=target.lease_owner,
        lease_until=_isoformat(target.lease_until),
        last_status=target.last_status,
        last_error_code=target.last_error_code,
        last_crawled_at=_isoformat(target.last_crawled_at),
        next_crawl_at=_isoformat(target.next_crawl_at),
        last_crawled_price=target.last_crawled_price,
    )


def format_target_info(target: CrawlTarget) -> str:
    lines = [
        f"target_id: {target.target_id}",
        f"mall_id: {target.mall_id}",
        f"product_url: {safe_url_for_log(target.product_url)}",
        f"enabled: {target.enabled}",
        f"crawl_interval_seconds: {target.crawl_interval_seconds}",
        f"crawl_status: {target.crawl_status}",
        f"lease_until: {_isoformat(target.lease_until) or 'null'}",
        f"last_status: {target.last_status or 'null'}",
        f"last_crawled_at: {_isoformat(target.last_crawled_at) or 'null'}",
        f"next_crawl_at: {_isoformat(target.next_crawl_at) or 'null'}",
    ]
    return "\n".join(lines)


def format_snapshot_block(title: str, snapshot: TargetSnapshot | None) -> str:
    if snapshot is None:
        return f"========== {title} ==========\n(not available)"
    lines = [
        f"========== {title} ==========",
        f"target_id: {snapshot.target_id}",
        f"status: {snapshot.crawl_status or 'null'}",
        f"last_status: {snapshot.last_status or 'null'}",
        f"last_price: {snapshot.last_crawled_price if snapshot.last_crawled_price is not None else 'null'}",
        f"next_crawl_at: {snapshot.next_crawl_at or 'null'}",
        f"lease_until: {snapshot.lease_until or 'null'}",
        f"lease_owner: {snapshot.lease_owner or 'null'}",
    ]
    if snapshot.last_error_code:
        lines.append(f"last_error_code: {snapshot.last_error_code}")
    return "\n".join(lines)


def preflight_target(
    target: CrawlTarget | None,
    *,
    target_id: str,
    now: datetime,
    worker_owner: str,
) -> tuple[SmokeExitCode, str]:
    if target is None:
        return SmokeExitCode.ERROR, f"Target not found: crawler_targets/{target_id}"
    if not target.enabled:
        return SmokeExitCode.ERROR, f"Target is disabled: {target_id}"
    if target.has_active_lease(now) and target.lease_owner != worker_owner:
        return SmokeExitCode.SKIP, "Target is currently leased by another worker"
    return SmokeExitCode.SUCCESS, ""


def _effective_run_at(target: CrawlTarget, now: datetime) -> datetime:
    """Explicit smoke runs treat a future next_crawl_at as due (orchestration only)."""
    if target.next_crawl_at is not None and target.next_crawl_at > now:
        return target.next_crawl_at
    return now


def _apply_timeout_override(timeout: float | None) -> None:
    if timeout is None:
        return
    os.environ["PRICEBRAIN_CRAWLER_TIMEOUT_SECONDS"] = str(timeout)
    clear_settings_cache()
    clear_crawler_config_cache()


def _apply_lease_override(lease_seconds: int | None) -> None:
    if lease_seconds is None:
        return
    os.environ["PRICEBRAIN_CRAWLER_MAX_TARGETS_PER_CYCLE"] = "1"
    os.environ["PRICEBRAIN_CRAWLER_LEASE_SECONDS"] = str(lease_seconds)
    clear_settings_cache()
    clear_crawler_config_cache()


def default_worker_factory(
    repo: CrawlTargetRepository,
    *,
    owner_id: str | None = None,
) -> CrawlerWorker:
    scheduler = CrawlerScheduler(repo)
    return CrawlerWorker(
        repo,
        scheduler,
        owner_id=owner_id or generate_worker_owner_id(),
    )


def verify_ingest_integrity(db: Any, ingest_response: dict[str, Any]) -> dict[str, Any]:
    listing_id = ingest_response.get("listing_id")
    product_id = ingest_response.get("product_id")
    result: dict[str, Any] = {
        "listing_id": listing_id,
        "product_id": product_id,
        "product_exists": False,
        "listing_exists": False,
        "price_history_count": 0,
        "price_history_appended": ingest_response.get("price_history_appended"),
    }
    if not listing_id or not product_id:
        return result

    result["product_exists"] = _document_exists(db, c.PRODUCTS, str(product_id))
    result["listing_exists"] = _document_exists(db, c.LISTINGS, str(listing_id))
    result["price_history_count"] = _price_history_count(db, str(listing_id))
    return result


def _document_exists(db: Any, collection: str, doc_id: str) -> bool:
    snapshot = db.collection(collection).document(doc_id).get()
    return bool(getattr(snapshot, "exists", False))


def _price_history_count(db: Any, listing_id: str) -> int:
    history_prefix = f"{c.LISTINGS}/{listing_id}/{c.PRICE_HISTORY}/"
    if hasattr(db, "paths"):
        return sum(1 for path in db.paths() if path.startswith(history_prefix))
    history_docs = (
        db.collection(c.LISTINGS)
        .document(listing_id)
        .collection(c.PRICE_HISTORY)
        .stream()
    )
    return sum(1 for _ in history_docs)


def _price_history_prices(db: Any, listing_id: str) -> list[int]:
    history_prefix = f"{c.LISTINGS}/{listing_id}/{c.PRICE_HISTORY}/"
    prices: list[int] = []
    if hasattr(db, "paths"):
        for path in sorted(db.paths()):
            if not path.startswith(history_prefix):
                continue
            data = db.get_document(path)
            if data and data.get("price") is not None:
                prices.append(int(data["price"]))
        return prices

    for snapshot in (
        db.collection(c.LISTINGS)
        .document(listing_id)
        .collection(c.PRICE_HISTORY)
        .stream()
    ):
        data = snapshot.to_dict() if hasattr(snapshot, "to_dict") else None
        if data and data.get("price") is not None:
            prices.append(int(data["price"]))
    return sorted(prices)


def verify_product_document(db: Any, product_id: str) -> dict[str, Any]:
    snapshot = db.collection(c.PRODUCTS).document(product_id).get()
    exists = bool(getattr(snapshot, "exists", False))
    data = snapshot.to_dict() if exists and hasattr(snapshot, "to_dict") else None
    return {
        "product_id": product_id,
        "exists": exists,
        "canonical_product_id": product_id if exists else None,
        "product_name": data.get("product_name") if data else None,
    }


def verify_listing_document(db: Any, listing_id: str) -> dict[str, Any]:
    snapshot = db.collection(c.LISTINGS).document(listing_id).get()
    exists = bool(getattr(snapshot, "exists", False))
    data = snapshot.to_dict() if exists and hasattr(snapshot, "to_dict") else None
    current_price = None
    if data and data.get("current_price") is not None:
        current_price = int(data["current_price"])
    return {
        "listing_id": listing_id,
        "exists": exists,
        "current_price": current_price,
    }


def verify_price_history_documents(db: Any, listing_id: str) -> dict[str, Any]:
    count = _price_history_count(db, listing_id)
    prices = _price_history_prices(db, listing_id)
    return {
        "listing_id": listing_id,
        "count": count,
        "prices": prices,
    }


def _apply_entity_verification(
    outcome: SmokeOutcome,
    db: Any,
    config: SmokeConfig,
    ingest_response: dict[str, Any],
) -> None:
    listing_id = str(ingest_response.get("listing_id") or "")
    product_id = str(ingest_response.get("product_id") or "")
    if config.verify_product and product_id:
        outcome.product_verification = verify_product_document(db, product_id)
    if config.verify_listing and listing_id:
        outcome.listing_verification = verify_listing_document(db, listing_id)
    if config.verify_price_history and listing_id:
        outcome.price_history_verification = verify_price_history_documents(db, listing_id)


def _lease_is_released(snapshot: TargetSnapshot | None) -> bool:
    if snapshot is None:
        return False
    return snapshot.crawl_status == CRAWL_STATUS_IDLE and not snapshot.lease_owner


def run_smoke(
    config: SmokeConfig,
    *,
    db_factory: FirestoreFactory | None = None,
    worker_factory: WorkerFactory | None = None,
    ingest_client_factory: IngestClientFactory | None = None,
    now: datetime | None = None,
) -> SmokeOutcome:
    run_at = now or utc_now()
    outcome = SmokeOutcome(target_id=config.target_id, exit_code=SmokeExitCode.SUCCESS)

    _apply_timeout_override(config.timeout)
    _apply_lease_override(config.lease_seconds)

    db = (db_factory or get_firestore_client)()
    repo = CrawlTargetRepository(db)
    if worker_factory is not None:
        worker = worker_factory(repo)
    else:
        worker = default_worker_factory(repo, owner_id=config.owner_id)

    target = repo.get(config.target_id)
    outcome.before = snapshot_target(target, target_id=config.target_id)

    exit_code, message = preflight_target(
        target,
        target_id=config.target_id,
        now=run_at,
        worker_owner=worker.owner_id,
    )
    if exit_code != SmokeExitCode.SUCCESS:
        outcome.exit_code = exit_code
        outcome.message = message
        outcome.skipped = exit_code == SmokeExitCode.SKIP
        return outcome

    run_at = _effective_run_at(target, run_at)

    ingest_client: IngestClient | None = None
    try:
        if config.ingest:
            outcome.ingest_attempted = True
            ingest_client = (ingest_client_factory or IngestClient)()

        worker_result = worker.run_once(
            ingest=config.ingest,
            target_id=config.target_id,
            max_targets=1,
            lease_seconds=config.lease_seconds,
            ingest_client=ingest_client,
            now=run_at,
        )

        outcome.claimed = bool(worker_result.claimed_targets)
        outcome.skipped = worker_result.skipped_targets > 0 and not outcome.claimed

        if worker_result.results:
            outcome.crawl_result = worker_result.results[0]
            if outcome.crawl_result.status == CrawlerStatus.INGEST_ERROR:
                outcome.ingest_status = "INGEST_ERROR"
            elif config.ingest and outcome.crawl_result.status == CrawlerStatus.SUCCESS:
                outcome.ingest_status = "SUCCESS"
            elif config.ingest:
                outcome.ingest_status = None
        elif outcome.claimed:
            outcome.message = "Target claimed but no crawl result returned"
            outcome.exit_code = SmokeExitCode.ERROR
            return outcome
        else:
            outcome.exit_code = SmokeExitCode.SKIP
            outcome.message = "Target was not claimed (lease or due window)"
            return outcome

    except Exception as exc:
        outcome.exit_code = SmokeExitCode.ERROR
        outcome.message = str(exc)
        return outcome
    finally:
        if ingest_client is not None:
            ingest_client.close()

    after_target = repo.get(config.target_id)
    outcome.after = snapshot_target(after_target, target_id=config.target_id)
    outcome.lease_released = _lease_is_released(outcome.after)

    if config.ingest and outcome.ingest_status == "SUCCESS" and outcome.crawl_result:
        ingest_response = outcome.crawl_result.ingest_response
        if isinstance(ingest_response, dict):
            outcome.ingest_integrity = verify_ingest_integrity(db, ingest_response)
            outcome.firestore_verified = bool(
                outcome.ingest_integrity.get("product_exists")
                and outcome.ingest_integrity.get("listing_exists")
            )
            if (
                config.verify_product
                or config.verify_listing
                or config.verify_price_history
            ):
                _apply_entity_verification(outcome, db, config, ingest_response)
    elif config.verify_firestore:
        outcome.firestore_verified = outcome.before is not None and outcome.after is not None

    outcome.exit_code = SmokeExitCode.SUCCESS
    return outcome


def render_smoke_outcome(
    outcome: SmokeOutcome,
    *,
    verify_firestore: bool,
    json_output: bool,
    secrets: list[str] | None = None,
) -> str:
    if json_output:
        payload = outcome.to_public_dict()
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        return redact_secrets(text, secrets or [])

    parts: list[str] = []
    if outcome.message and outcome.exit_code != SmokeExitCode.SUCCESS:
        parts.append(outcome.message)
        return redact_secrets("\n".join(parts), secrets or [])

    if verify_firestore:
        parts.append(format_snapshot_block("BEFORE", outcome.before))

    if outcome.crawl_result is not None:
        parts.append("========== CRAWL ==========")
        parts.append(f"status: {outcome.crawl_result.status.value}")
        if outcome.error_code:
            parts.append(f"error_code: {outcome.error_code}")
        if outcome.ingest_attempted:
            parts.append(f"ingest_status: {outcome.ingest_status or 'null'}")
    elif outcome.before is not None:
        parts.append(format_target_info_from_snapshot(outcome.before, title="TARGET"))

    if verify_firestore:
        parts.append(format_snapshot_block("AFTER", outcome.after))
    elif outcome.before is not None and outcome.after is None:
        parts.append(format_target_info_from_snapshot(outcome.before, title="TARGET"))

    if outcome.ingest_integrity:
        parts.append("========== INGEST INTEGRITY ==========")
        parts.append(json.dumps(outcome.ingest_integrity, ensure_ascii=False, indent=2))

    if outcome.product_verification:
        parts.append("========== VERIFY PRODUCT ==========")
        parts.append(json.dumps(outcome.product_verification, ensure_ascii=False, indent=2))

    if outcome.listing_verification:
        parts.append("========== VERIFY LISTING ==========")
        parts.append(json.dumps(outcome.listing_verification, ensure_ascii=False, indent=2))

    if outcome.price_history_verification:
        parts.append("========== VERIFY PRICE HISTORY ==========")
        parts.append(json.dumps(outcome.price_history_verification, ensure_ascii=False, indent=2))

    if not parts and outcome.before is not None:
        parts.append(format_target_info_from_snapshot(outcome.before, title="TARGET"))

    return redact_secrets("\n\n".join(part for part in parts if part), secrets or [])


def format_target_info_from_snapshot(snapshot: TargetSnapshot, *, title: str = "TARGET") -> str:
    lines = [
        f"========== {title} ==========",
        f"target_id: {snapshot.target_id}",
        f"mall_id: {snapshot.mall_id}",
        f"product_url: {snapshot.product_url}",
        f"enabled: {snapshot.enabled}",
        f"crawl_interval_seconds: {snapshot.crawl_interval_seconds}",
        f"crawl_status: {snapshot.crawl_status}",
        f"lease_until: {snapshot.lease_until or 'null'}",
        f"last_status: {snapshot.last_status or 'null'}",
        f"last_crawled_at: {snapshot.last_crawled_at or 'null'}",
        f"next_crawl_at: {snapshot.next_crawl_at or 'null'}",
    ]
    return "\n".join(lines)


def load_target_preview(db: Any, target_id: str) -> CrawlTarget | None:
    repo = CrawlTargetRepository(db)
    return repo.get(target_id)


def print_startup_target_info(target: CrawlTarget) -> str:
    return format_target_info(target)
