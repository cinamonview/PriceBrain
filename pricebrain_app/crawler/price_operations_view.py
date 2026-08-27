"""Read-only GPU price operations queries over listings and price_history."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pricebrain_app.crawler.operations_view import (
    TargetListFilter,
    _get_listing_document_data,
    _read_price_history,
    resolve_listing_id_for_target,
)
from pricebrain_app.crawler.operations_read_cache import get_operations_read_cache
from pricebrain_app.crawler.price_calculations import (
    build_price_history_views,
    build_price_snapshot,
    build_price_summary,
)
from pricebrain_app.crawler.price_ops_models import (
    GpuPriceStatusSummary,
    PriceChangeClassification,
    PriceHistoryEntryView,
    PriceSnapshot,
    PriceSummary,
)
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.repository import constants as c


@dataclass(frozen=True)
class PriceListFilter:
    mall_id: str | None = None
    category: str | None = None
    tag: str | None = None
    brand: str | None = None
    priority_min: int | None = None
    target_id: str | None = None


class PriceOperationsView:
    """Read-only price snapshot and summary queries for crawl targets."""

    def __init__(self, target_repository: CrawlTargetRepository, db: Any) -> None:
        self._targets = target_repository
        self._db = db

    def get_price_summary(self, target_id: str) -> PriceSummary | None:
        cache = get_operations_read_cache()
        if cache is not None and target_id in cache.price_summaries:
            return cache.price_summaries[target_id]

        target = self._targets.get(target_id)
        if target is None:
            return None
        summary = self._build_summary_for_target(target)
        if cache is not None:
            cache.price_summaries[target_id] = summary
        return summary

    def get_current_price(self, target_id: str) -> PriceSnapshot | None:
        summary = self.get_price_summary(target_id)
        if summary is None:
            return None
        return build_price_snapshot(summary)

    def get_price_history(self, target_id: str) -> list[PriceHistoryEntryView]:
        target = self._targets.get(target_id)
        if target is None:
            return []
        listing_id = resolve_listing_id_for_target(target)
        if listing_id is None:
            return []
        return build_price_history_views(_read_price_history(self._db, listing_id))

    def list_price_summaries(
        self,
        *,
        filters: PriceListFilter | None = None,
    ) -> list[PriceSummary]:
        flt = filters or PriceListFilter()
        if flt.target_id is not None:
            summary = self.get_price_summary(flt.target_id.strip())
            return [summary] if summary is not None else []

        targets = self._targets.list_all(
            mall_id=flt.mall_id,
            category=flt.category or "gpu",
            tag=flt.tag,
            priority_min=flt.priority_min,
        )
        if flt.brand is not None:
            brand = flt.brand.strip().lower()
            targets = [
                target
                for target in targets
                if brand in {item.lower() for item in target.tags}
            ]

        summaries = [self._build_summary_for_target(target) for target in targets]
        summaries.sort(
            key=lambda item: (
                item.observed_at is None,
                item.observed_at,
                item.target_id,
            ),
            reverse=True,
        )
        return summaries

    def list_price_changes(
        self,
        *,
        classification: PriceChangeClassification,
        filters: PriceListFilter | None = None,
    ) -> list[PriceSummary]:
        return [
            summary
            for summary in self.list_price_summaries(filters=filters)
            if summary.classification is classification
        ]

    def list_price_drops(self, *, filters: PriceListFilter | None = None) -> list[PriceSummary]:
        return self.list_price_changes(
            classification=PriceChangeClassification.PRICE_DOWN,
            filters=filters,
        )

    def list_price_increases(self, *, filters: PriceListFilter | None = None) -> list[PriceSummary]:
        return self.list_price_changes(
            classification=PriceChangeClassification.PRICE_UP,
            filters=filters,
        )

    def summarize_gpu_prices(self, *, filters: PriceListFilter | None = None) -> GpuPriceStatusSummary:
        summaries = self.list_price_summaries(filters=filters)
        with_price = [item for item in summaries if item.has_price_observation]
        current_prices = [item.current_price for item in with_price if item.current_price is not None]

        return GpuPriceStatusSummary(
            targets=len(summaries),
            with_price=len(with_price),
            without_price=len(summaries) - len(with_price),
            price_down=sum(
                1 for item in summaries if item.classification is PriceChangeClassification.PRICE_DOWN
            ),
            price_up=sum(
                1 for item in summaries if item.classification is PriceChangeClassification.PRICE_UP
            ),
            unchanged=sum(
                1 for item in summaries if item.classification is PriceChangeClassification.UNCHANGED
            ),
            no_history=sum(
                1 for item in summaries if item.classification is PriceChangeClassification.NO_HISTORY
            ),
            invalid_price=sum(
                1
                for item in summaries
                if item.classification is PriceChangeClassification.INVALID_PRICE
            ),
            average_current_price=(
                round(sum(current_prices) / len(current_prices), 2) if current_prices else None
            ),
            lowest_current_price=min(current_prices) if current_prices else None,
            highest_current_price=max(current_prices) if current_prices else None,
        )

    def _build_summary_for_target(self, target) -> PriceSummary:
        listing_id = resolve_listing_id_for_target(target)
        listing_data = None
        history_entries: list[dict[str, Any]] = []
        product_id = None
        listing_exists = False

        if listing_id is not None:
            listing_exists, listing_data = _get_listing_document_data(self._db, listing_id)
            if listing_exists and listing_data is not None:
                product_id = listing_data.get("product_id")
            history_entries = _read_price_history(self._db, listing_id)

        return build_price_summary(
            target,
            listing_id=listing_id,
            listing_data=listing_data,
            history_entries=history_entries,
            product_id=str(product_id) if product_id else None,
            listing_exists=listing_exists,
        )


def price_filter_from_target_filter(target_filter: TargetListFilter) -> PriceListFilter:
    return PriceListFilter(
        mall_id=target_filter.mall_id,
        category=target_filter.category,
        tag=target_filter.tag,
        priority_min=target_filter.priority_min,
    )
