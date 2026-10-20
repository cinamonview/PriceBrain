"""Window statistics over price_history step series — PRD §11, §14.

price_history is appended only when the price changes (docs/05 §3.9), so a
listing's price is a step function: each point holds until the next one. All
window statistics are therefore time-weighted, and the price in effect at the
window start is carried in from the last point before it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone

from pricebrain_app.analysis.models import PricePoint, PriceStats

_SECONDS_PER_DAY = 86_400


def ensure_utc(value: datetime) -> datetime:
    """Firestore returns aware datetimes; treat naive values as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def normalize_points(points: Iterable[PricePoint], *, now: datetime) -> list[PricePoint]:
    """Sort by crawled_at, drop future and non-positive prices, keep last per timestamp."""
    by_time: dict[datetime, int] = {}
    for point in points:
        crawled_at = ensure_utc(point.crawled_at)
        if crawled_at > now or point.price <= 0:
            continue
        by_time[crawled_at] = int(point.price)
    return [PricePoint(crawled_at=at, price=by_time[at]) for at in sorted(by_time)]


def _window_segments(
    points: list[PricePoint], *, window_start: datetime
) -> list[PricePoint]:
    """Segments in effect inside the window; the carried-in price starts at window_start."""
    carried: PricePoint | None = None
    inside: list[PricePoint] = []
    for point in points:
        if point.crawled_at <= window_start:
            carried = point
        else:
            inside.append(point)
    if carried is None:
        return inside
    return [PricePoint(crawled_at=window_start, price=carried.price), *inside]


def _rate(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator * 100, 2)


def empty_stats(*, window_days: int, now: datetime) -> PriceStats:
    return PriceStats(
        window_days=window_days,
        window_start=now - timedelta(days=window_days),
        window_end=now,
        observed_from=None,
        coverage_days=0.0,
        data_points=0,
        current_price=None,
        min_price=None,
        max_price=None,
        average_price=None,
        median_price=None,
        price_range=None,
        start_price=None,
        price_change=None,
        price_change_rate=None,
        price_percentile=None,
        diff_from_min=None,
        diff_from_average_rate=None,
    )


def compute_price_stats(
    points: Iterable[PricePoint],
    *,
    window_days: int,
    now: datetime,
) -> PriceStats:
    now = ensure_utc(now)
    window_start = now - timedelta(days=window_days)
    segments = _window_segments(normalize_points(points, now=now), window_start=window_start)
    if not segments:
        return empty_stats(window_days=window_days, now=now)

    ends = [segment.crawled_at for segment in segments[1:]] + [now]
    weights = [(end - segment.crawled_at).total_seconds() for segment, end in zip(segments, ends)]
    total = sum(weights)
    if total <= 0:
        weights = [1.0] * len(segments)
        total = float(len(segments))

    prices = [segment.price for segment in segments]
    current = prices[-1]
    start = prices[0]
    lowest = min(prices)
    average = round(sum(price * weight for price, weight in zip(prices, weights)) / total)

    median = prices[-1]
    cumulative = 0.0
    for price, weight in sorted(zip(prices, weights)):
        cumulative += weight
        if cumulative >= total / 2:
            median = price
            break

    below_current = sum(weight for price, weight in zip(prices, weights) if price < current)
    observed_from = segments[0].crawled_at

    return PriceStats(
        window_days=window_days,
        window_start=window_start,
        window_end=now,
        observed_from=observed_from,
        coverage_days=round((now - observed_from).total_seconds() / _SECONDS_PER_DAY, 2),
        data_points=len(segments),
        current_price=current,
        min_price=lowest,
        max_price=max(prices),
        average_price=average,
        median_price=median,
        price_range=max(prices) - lowest,
        start_price=start,
        price_change=current - start,
        price_change_rate=_rate(current - start, start),
        price_percentile=round(below_current / total * 100, 1),
        diff_from_min=current - lowest,
        diff_from_average_rate=_rate(current - average, average),
    )


def lowest_price_series(series_by_listing: Mapping[str, list[PricePoint]]) -> list[PricePoint]:
    """Merge listing step series into the product's lowest-price step series."""
    events: list[tuple[datetime, str, int]] = sorted(
        (point.crawled_at, listing_id, point.price)
        for listing_id, points in series_by_listing.items()
        for point in points
    )
    current: dict[str, int] = {}
    merged: list[PricePoint] = []
    index = 0
    while index < len(events):
        at = events[index][0]
        while index < len(events) and events[index][0] == at:
            _, listing_id, price = events[index]
            current[listing_id] = price
            index += 1
        lowest = min(current.values())
        if not merged or merged[-1].price != lowest:
            merged.append(PricePoint(crawled_at=at, price=lowest))
    return merged
