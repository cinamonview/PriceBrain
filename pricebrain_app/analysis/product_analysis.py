"""Product-level price analysis across listings — PRD §11.3, §13."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pricebrain_app.analysis.models import (
    ListingPriceAnalysis,
    PricePoint,
    ProductPriceAnalysis,
    SeriesPoint,
)
from pricebrain_app.analysis.price_stats import (
    compute_price_stats,
    ensure_utc,
    lowest_price_series,
    normalize_points,
)
from pricebrain_app.analysis.purchase import (
    DEFAULT_RULES,
    TREND_WINDOW_DAYS,
    PurchaseRules,
    assess_purchase,
)


@dataclass(frozen=True)
class ListingHistory:
    listing_id: str
    data: Mapping[str, Any]
    points: Sequence[PricePoint]


def is_listing_available(data: Mapping[str, Any]) -> bool:
    if data.get("availability") is False:
        return False
    return str(data.get("status", "AVAILABLE")).upper() == "AVAILABLE"


def _points_with_listing_fallback(history: ListingHistory, *, now: datetime) -> list[PricePoint]:
    """Use price_history; fall back to the listing's current_price when history is empty."""
    points = normalize_points(history.points, now=now)
    if points:
        return points
    price = history.data.get("current_price")
    crawled_at = history.data.get("crawled_at")
    if isinstance(price, (int, float)) and isinstance(crawled_at, datetime):
        return normalize_points([PricePoint(crawled_at=crawled_at, price=int(price))], now=now)
    return []


def analyze_product(
    *,
    product_id: str,
    product_name: str | None,
    listings: Sequence[ListingHistory],
    window_days: int,
    now: datetime,
    rules: PurchaseRules = DEFAULT_RULES,
) -> ProductPriceAnalysis:
    now = ensure_utc(now)
    listing_results: list[ListingPriceAnalysis] = []
    available_series: dict[str, list[PricePoint]] = {}

    for history in listings:
        points = _points_with_listing_fallback(history, now=now)
        available = is_listing_available(history.data)
        if available and points:
            available_series[history.listing_id] = points
        listing_results.append(
            ListingPriceAnalysis(
                listing_id=history.listing_id,
                mall_id=history.data.get("mall_id"),
                seller_id=history.data.get("seller_id"),
                product_url=history.data.get("product_url"),
                available=available,
                stats=compute_price_stats(points, window_days=window_days, now=now),
            )
        )

    listing_results.sort(
        key=lambda item: (
            not item.available,
            item.stats.current_price is None,
            item.stats.current_price or 0,
            item.listing_id,
        )
    )
    lowest = next(
        (item for item in listing_results if item.available and item.stats.current_price is not None),
        None,
    )

    series = lowest_price_series(available_series)
    stats = compute_price_stats(series, window_days=window_days, now=now)
    trend_stats = compute_price_stats(series, window_days=TREND_WINDOW_DAYS, now=now)
    window_start = stats.window_start
    carried = [point for point in series if point.crawled_at <= window_start][-1:]
    visible = carried + [point for point in series if point.crawled_at > window_start]

    return ProductPriceAnalysis(
        product_id=product_id,
        product_name=product_name,
        window_days=window_days,
        generated_at=now,
        lowest_listing_id=lowest.listing_id if lowest else None,
        stats=stats,
        purchase=assess_purchase(stats, trend_stats, rules),
        listings=listing_results,
        lowest_price_series=[
            SeriesPoint(crawled_at=max(point.crawled_at, window_start), price=point.price)
            for point in visible
        ],
    )
