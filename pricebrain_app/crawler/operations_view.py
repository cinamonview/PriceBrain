"""Read-only crawler operations and observability queries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pricebrain_app.crawler.gpu_catalog import gpu_model_label_from_target
from pricebrain_app.crawler.logging_utils import safe_url_for_log
from pricebrain_app.crawler.malls.ssg import extract_ssg_item_id
from pricebrain_app.crawler.metrics import get_crawler_metrics
from pricebrain_app.crawler.operations_read_cache import get_operations_read_cache
from pricebrain_app.crawler.ops_models import (
    CrawlerFailureView,
    CrawlerOpsSummary,
    GpuCatalogSummary,
    MallOpsSummary,
    PriceChangeView,
    ScheduleEntry,
    TargetOperationalView,
    is_failed_last_status,
)
from pricebrain_app.crawler.results import CrawlerStatus
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.targets import CRAWL_STATUS_CLAIMED, CrawlTarget, utc_now
from pricebrain_app.crawler.worker_health import get_worker_health
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.listing_repository import build_listing_document_id


@dataclass(frozen=True)
class TargetListFilter:
    mall_id: str | None = None
    enabled: bool | None = None
    category: str | None = None
    tag: str | None = None
    priority_min: int | None = None
    due_only: bool = False
    failed_only: bool = False


def derive_operational_state(target: CrawlTarget, now: datetime) -> str:
    if not target.enabled:
        return "DISABLED"
    if target.has_active_lease(now) or target.crawl_status == CRAWL_STATUS_CLAIMED:
        return "CLAIMED"
    if target.next_crawl_at is None or target.next_crawl_at <= now:
        return "DUE"
    return "ENABLED"


def is_target_due(target: CrawlTarget, now: datetime) -> bool:
    if not target.enabled:
        return False
    if target.has_active_lease(now):
        return False
    return target.next_crawl_at is None or target.next_crawl_at <= now


def build_target_view(target: CrawlTarget, *, now: datetime | None = None) -> TargetOperationalView:
    run_at = now or utc_now()
    return TargetOperationalView(
        target_id=target.target_id,
        mall_id=target.mall_id,
        product_url=safe_url_for_log(target.product_url),
        enabled=target.enabled,
        crawl_interval_seconds=target.crawl_interval_seconds,
        external_product_id=target.external_product_id,
        product_name=target.product_name,
        category=target.category,
        tags=tuple(target.tags),
        priority=target.priority,
        crawl_status=target.crawl_status,
        lease_owner=target.lease_owner,
        lease_until=target.lease_until,
        last_crawled_at=target.last_crawled_at,
        next_crawl_at=target.next_crawl_at,
        last_status=target.last_status,
        last_error_code=target.last_error_code,
        last_error_message=target.last_error_message,
        last_crawled_price=target.last_crawled_price,
        created_at=target.created_at,
        updated_at=target.updated_at,
        operational_state=derive_operational_state(target, run_at),
        is_due=is_target_due(target, run_at),
        is_failed=is_failed_last_status(target.last_status),
        has_active_lease=target.has_active_lease(run_at),
    )


class CrawlerOperationsView:
    """Query crawler_targets and related Firestore data for operations."""

    def __init__(self, target_repository: CrawlTargetRepository, db: Any) -> None:
        self._targets = target_repository
        self._db = db

    def _fetch_targets(
        self,
        *,
        mall_id: str | None = None,
        enabled: bool | None = None,
        category: str | None = None,
        tag: str | None = None,
        priority_min: int | None = None,
    ) -> list[CrawlTarget]:
        cache = get_operations_read_cache()
        key = (mall_id, enabled, category, tag, priority_min)
        if cache is not None and key in cache.crawler_targets:
            return cache.crawler_targets[key]
        result = self._targets.list_all(
            mall_id=mall_id,
            enabled=enabled,
            category=category,
            tag=tag,
            priority_min=priority_min,
        )
        if cache is not None:
            cache.crawler_targets[key] = result
        return result

    def list_targets(
        self,
        *,
        filters: TargetListFilter | None = None,
        now: datetime | None = None,
    ) -> list[TargetOperationalView]:
        run_at = now or utc_now()
        flt = filters or TargetListFilter()
        raw = self._fetch_targets(
            mall_id=flt.mall_id,
            enabled=flt.enabled,
            category=flt.category,
            tag=flt.tag,
            priority_min=flt.priority_min,
        )
        views = [build_target_view(target, now=run_at) for target in raw]
        if flt.due_only:
            views = [view for view in views if view.is_due]
        if flt.failed_only:
            views = [view for view in views if view.is_failed]
        return views

    def get_target(self, target_id: str, *, now: datetime | None = None) -> TargetOperationalView | None:
        target = self._targets.get(target_id)
        if target is None:
            return None
        return build_target_view(target, now=now or utc_now())

    def summarize(self, *, now: datetime | None = None) -> CrawlerOpsSummary:
        run_at = now or utc_now()
        targets = self._fetch_targets()
        enabled = [target for target in targets if target.enabled]
        disabled = [target for target in targets if not target.enabled]
        due = [target for target in enabled if is_target_due(target, run_at)]
        claimed = [
            target
            for target in targets
            if target.has_active_lease(run_at) or target.crawl_status == CRAWL_STATUS_CLAIMED
        ]
        success = [target for target in targets if target.last_status == CrawlerStatus.SUCCESS.value]
        failed = [target for target in targets if is_failed_last_status(target.last_status)]
        lease_active = [target for target in targets if target.has_active_lease(run_at)]
        return CrawlerOpsSummary(
            total_targets=len(targets),
            enabled_targets=len(enabled),
            disabled_targets=len(disabled),
            due_targets=len(due),
            claimed_targets=len(claimed),
            success_targets=len(success),
            failed_targets=len(failed),
            lease_active_targets=len(lease_active),
        )

    def summarize_by_mall(self, *, now: datetime | None = None) -> list[MallOpsSummary]:
        run_at = now or utc_now()
        malls: dict[str, list[CrawlTarget]] = {}
        for target in self._fetch_targets():
            malls.setdefault(target.mall_id, []).append(target)

        summaries: list[MallOpsSummary] = []
        for mall_id in sorted(malls):
            items = malls[mall_id]
            enabled = [item for item in items if item.enabled]
            summaries.append(
                MallOpsSummary(
                    mall_id=mall_id,
                    total=len(items),
                    enabled=len(enabled),
                    disabled=len(items) - len(enabled),
                    due=len([item for item in enabled if is_target_due(item, run_at)]),
                    success=len(
                        [item for item in items if item.last_status == CrawlerStatus.SUCCESS.value]
                    ),
                    failed=len([item for item in items if is_failed_last_status(item.last_status)]),
                    lease_active=len([item for item in items if item.has_active_lease(run_at)]),
                )
            )
        return summaries

    def summarize_gpu_catalog(self) -> GpuCatalogSummary:
        targets = self._fetch_targets(category="gpu")
        enabled = [target for target in targets if target.enabled]
        disabled = [target for target in targets if not target.enabled]
        model_counts: dict[str, int] = {}
        for target in targets:
            label = gpu_model_label_from_target(
                product_name=target.product_name,
                tags=target.tags,
            )
            model_counts[label] = model_counts.get(label, 0) + 1
        return GpuCatalogSummary(
            total=len(targets),
            enabled=len(enabled),
            disabled=len(disabled),
            model_counts=tuple(sorted(model_counts.items(), key=lambda item: (-item[1], item[0]))),
        )

    def list_recent_failures(
        self,
        *,
        limit: int = 20,
        mall_id: str | None = None,
    ) -> list[CrawlerFailureView]:
        targets = self._fetch_targets(mall_id=mall_id)
        failed = [target for target in targets if is_failed_last_status(target.last_status)]
        failed.sort(
            key=lambda item: item.last_crawled_at or item.updated_at or datetime.min.replace(tzinfo=utc_now().tzinfo),
            reverse=True,
        )
        views: list[CrawlerFailureView] = []
        for target in failed[: max(int(limit), 0)]:
            views.append(
                CrawlerFailureView(
                    target_id=target.target_id,
                    mall_id=target.mall_id,
                    product_url=safe_url_for_log(target.product_url),
                    last_status=target.last_status,
                    last_error_code=target.last_error_code,
                    last_error_message=target.last_error_message,
                    last_crawled_at=target.last_crawled_at,
                    next_crawl_at=target.next_crawl_at,
                )
            )
        return views

    def list_schedule(self, *, now: datetime | None = None) -> list[ScheduleEntry]:
        run_at = now or utc_now()
        entries: list[ScheduleEntry] = []
        for target in self._targets.list_enabled():
            due = is_target_due(target, run_at)
            seconds = None
            if target.next_crawl_at is not None and not due:
                seconds = int((target.next_crawl_at - run_at).total_seconds())
            entries.append(
                ScheduleEntry(
                    target_id=target.target_id,
                    mall_id=target.mall_id,
                    next_crawl_at=target.next_crawl_at,
                    seconds_until_due=seconds,
                    is_due=due,
                )
            )
        entries.sort(key=lambda item: (item.next_crawl_at is None, item.next_crawl_at or run_at))
        return entries

    def get_price_change_for_target(self, target_id: str) -> PriceChangeView | None:
        target = self._targets.get(target_id)
        if target is None:
            return None
        listing_id = resolve_listing_id_for_target(target)
        if listing_id is None:
            return PriceChangeView(
                listing_id=None,
                product_name=None,
                current_price=target.last_crawled_price,
                previous_price=None,
                price_change=None,
                last_crawled_at=target.last_crawled_at,
            )
        return get_price_change_for_listing(self._db, listing_id, fallback_price=target.last_crawled_price)

    def status_payload(self, *, now: datetime | None = None) -> dict[str, Any]:
        return {
            "summary": self.summarize(now=now).to_dict(),
            "malls": [item.to_dict() for item in self.summarize_by_mall(now=now)],
            "gpu_catalog": self.summarize_gpu_catalog().to_dict(),
            "metrics": get_crawler_metrics().to_dict(),
            "worker_health": get_worker_health().to_dict(),
        }


def resolve_listing_id_for_target(target: CrawlTarget) -> str | None:
    mall = target.mall_id.strip().lower()
    if mall == "ssg":
        item_id = extract_ssg_item_id(target.product_url)
        if item_id:
            return build_listing_document_id(mall, item_id)
    return None


def get_price_change_for_listing(
    db: Any,
    listing_id: str,
    *,
    fallback_price: int | None = None,
) -> PriceChangeView:
    exists, listing_data = _get_listing_document_data(db, listing_id)

    product_name = None
    current_price = fallback_price
    last_crawled_at = None
    if exists and listing_data:
        product_name = listing_data.get("normalized_product_name") or listing_data.get("raw_product_name")
        if listing_data.get("current_price") is not None:
            current_price = int(listing_data["current_price"])
        last_crawled_at = listing_data.get("crawled_at")

    history_entries = _read_price_history(db, listing_id)
    previous_price = None
    price_change = None
    if history_entries:
        latest = history_entries[-1]
        if latest.get("price") is not None:
            current_price = int(latest["price"])
        if latest.get("crawled_at") is not None:
            last_crawled_at = latest["crawled_at"]
        if latest.get("previous_price") is not None:
            previous_price = int(latest["previous_price"])
        if latest.get("price_change") is not None:
            price_change = int(latest["price_change"])

    return PriceChangeView(
        listing_id=listing_id,
        product_name=product_name,
        current_price=current_price,
        previous_price=previous_price,
        price_change=price_change,
        last_crawled_at=last_crawled_at,
    )


def _get_listing_document_data(
    db: Any,
    listing_id: str,
) -> tuple[bool, dict[str, Any] | None]:
    cache = get_operations_read_cache()
    if cache is not None and listing_id in cache.listing_data:
        return cache.listing_data[listing_id]

    listing_doc = db.collection(c.LISTINGS).document(listing_id).get()
    exists = getattr(listing_doc, "exists", False)
    data = listing_doc.to_dict() if exists else None
    result = (exists, data)
    if cache is not None:
        cache.listing_data[listing_id] = result
    return result


def _read_price_history(db: Any, listing_id: str) -> list[dict[str, Any]]:
    cache = get_operations_read_cache()
    if cache is not None and listing_id in cache.price_history:
        return cache.price_history[listing_id]

    prefix = f"{c.LISTINGS}/{listing_id}/{c.PRICE_HISTORY}/"
    if hasattr(db, "paths"):
        entries: list[dict[str, Any]] = []
        for path in sorted(db.paths()):
            if not path.startswith(prefix):
                continue
            data = db.get_document(path)
            if data:
                entries.append(dict(data))
        entries.sort(key=lambda item: item.get("crawled_at") or datetime.min.replace(tzinfo=utc_now().tzinfo))
    else:
        snapshots = (
            db.collection(c.LISTINGS)
            .document(listing_id)
            .collection(c.PRICE_HISTORY)
            .stream()
        )
        entries = [dict(snapshot.to_dict() or {}) for snapshot in snapshots]
        entries.sort(key=lambda item: item.get("crawled_at") or datetime.min.replace(tzinfo=utc_now().tzinfo))

    if cache is not None:
        cache.price_history[listing_id] = entries
    return entries
