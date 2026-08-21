"""Pure price observation calculations — no Firestore or crawler writes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pricebrain_app.crawler.logging_utils import safe_url_for_log
from pricebrain_app.crawler.price_ops_models import (
    PriceChangeClassification,
    PriceHistoryEntryView,
    PriceSnapshot,
    PriceSummary,
)
from pricebrain_app.crawler.targets import CrawlTarget, parse_datetime


def is_valid_price(price: int | None) -> bool:
    return price is not None and price > 0


def calculate_price_change(current: int | None, previous: int | None) -> int | None:
    if not is_valid_price(current) or not is_valid_price(previous):
        return None
    return int(current) - int(previous)


def calculate_price_change_percent(current: int | None, previous: int | None) -> float | None:
    if not is_valid_price(current) or not is_valid_price(previous):
        return None
    if int(previous) == 0:
        return None
    return round((int(current) - int(previous)) / int(previous) * 100, 2)


def classify_price_change(
    current: int | None,
    previous: int | None,
    *,
    has_history: bool,
) -> PriceChangeClassification:
    if not is_valid_price(current):
        if not has_history:
            return PriceChangeClassification.NO_HISTORY
        return PriceChangeClassification.INVALID_PRICE
    if previous is None or not is_valid_price(previous):
        return PriceChangeClassification.NO_HISTORY
    if current == previous:
        return PriceChangeClassification.UNCHANGED
    if current < previous:
        return PriceChangeClassification.PRICE_DOWN
    return PriceChangeClassification.PRICE_UP


def build_price_summary(
    target: CrawlTarget,
    *,
    listing_id: str | None,
    listing_data: dict[str, Any] | None,
    history_entries: list[dict[str, Any]],
    product_id: str | None = None,
) -> PriceSummary:
    prices = _history_prices(history_entries)
    current_price, previous_price, price_change, observed_at = _resolve_current_and_previous(
        listing_data,
        history_entries,
    )
    if _should_suppress_price_observation(target, history_entries):
        current_price = None
        previous_price = None
        price_change = None

    first_price = prices[0] if prices else None
    lowest_price = min(prices) if prices else None
    highest_price = max(prices) if prices else None
    product_name = _resolve_product_name(target, listing_data)
    classification = classify_price_change(
        current_price,
        previous_price,
        has_history=bool(history_entries),
    )
    has_observation = is_valid_price(current_price)

    return PriceSummary(
        target_id=target.target_id,
        product_id=product_id,
        listing_id=listing_id,
        mall_id=target.mall_id,
        external_product_id=target.external_product_id,
        product_url=safe_url_for_log(target.product_url),
        product_name=product_name,
        current_price=current_price,
        previous_price=previous_price,
        price_change=price_change,
        price_change_percent=calculate_price_change_percent(current_price, previous_price),
        first_price=first_price,
        lowest_price=lowest_price,
        highest_price=highest_price,
        observed_at=observed_at,
        history_count=len(history_entries),
        classification=classification,
        has_price_observation=has_observation,
    )


def build_price_snapshot(summary: PriceSummary) -> PriceSnapshot:
    return PriceSnapshot(
        target_id=summary.target_id,
        product_id=summary.product_id,
        listing_id=summary.listing_id,
        mall_id=summary.mall_id,
        external_product_id=summary.external_product_id,
        product_url=summary.product_url,
        product_name=summary.product_name,
        price=summary.current_price,
        previous_price=summary.previous_price,
        price_change=summary.price_change,
        price_change_percent=summary.price_change_percent,
        observed_at=summary.observed_at,
        classification=summary.classification,
    )


def build_price_history_views(history_entries: list[dict[str, Any]]) -> list[PriceHistoryEntryView]:
    views: list[PriceHistoryEntryView] = []
    for entry in history_entries:
        price = _optional_int(entry.get("price"))
        previous_price = _optional_int(entry.get("previous_price"))
        price_change = _optional_int(entry.get("price_change"))
        if price_change is None:
            price_change = calculate_price_change(price, previous_price)
        views.append(
            PriceHistoryEntryView(
                observed_at=parse_datetime(entry.get("crawled_at")),
                price=price,
                previous_price=previous_price,
                price_change=price_change,
            )
        )
    return views


def _should_suppress_price_observation(target: CrawlTarget, history_entries: list[dict[str, Any]]) -> bool:
    if history_entries:
        return False
    if target.last_error_code in {"SSG_ACCESS_DENIED", "ACCESS_DENIED"}:
        return True
    if target.last_status == "HTTP_ERROR" and not is_valid_price(target.last_crawled_price):
        return True
    return False


def _resolve_product_name(target: CrawlTarget, listing_data: dict[str, Any] | None) -> str | None:
    if listing_data:
        name = listing_data.get("normalized_product_name") or listing_data.get("raw_product_name")
        if name:
            return str(name)
    return target.product_name


def _resolve_current_and_previous(
    listing_data: dict[str, Any] | None,
    history_entries: list[dict[str, Any]],
) -> tuple[int | None, int | None, int | None, datetime | None]:
    current_price: int | None = None
    previous_price: int | None = None
    price_change: int | None = None
    observed_at: datetime | None = None

    if history_entries:
        latest = history_entries[-1]
        current_price = _optional_int(latest.get("price"))
        observed_at = parse_datetime(latest.get("crawled_at"))
        previous_price = _optional_int(latest.get("previous_price"))
        price_change = _optional_int(latest.get("price_change"))
        if previous_price is None and len(history_entries) >= 2:
            previous_price = _optional_int(history_entries[-2].get("price"))
        if price_change is None:
            price_change = calculate_price_change(current_price, previous_price)
        return current_price, previous_price, price_change, observed_at

    if listing_data:
        current_price = _optional_int(listing_data.get("current_price"))
        observed_at = parse_datetime(listing_data.get("crawled_at"))
    return current_price, previous_price, price_change, observed_at


def _history_prices(history_entries: list[dict[str, Any]]) -> list[int]:
    prices: list[int] = []
    for entry in history_entries:
        price = _optional_int(entry.get("price"))
        if is_valid_price(price):
            prices.append(int(price))
    return prices


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
