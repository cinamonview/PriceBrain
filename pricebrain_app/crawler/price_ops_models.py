"""Price operations view models — read-only price snapshot DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class PriceChangeClassification(str, Enum):
    UNCHANGED = "UNCHANGED"
    PRICE_DOWN = "PRICE_DOWN"
    PRICE_UP = "PRICE_UP"
    NO_HISTORY = "NO_HISTORY"
    INVALID_PRICE = "INVALID_PRICE"


@dataclass(frozen=True)
class PriceSnapshot:
    target_id: str
    product_id: str | None
    listing_id: str | None
    mall_id: str
    external_product_id: str | None
    product_url: str
    product_name: str | None
    price: int | None
    previous_price: int | None
    price_change: int | None
    price_change_percent: float | None
    observed_at: datetime | None
    classification: PriceChangeClassification

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "product_id": self.product_id,
            "listing_id": self.listing_id,
            "mall_id": self.mall_id,
            "external_product_id": self.external_product_id,
            "product_url": self.product_url,
            "product_name": self.product_name,
            "price": self.price,
            "previous_price": self.previous_price,
            "price_change": self.price_change,
            "price_change_percent": self.price_change_percent,
            "observed_at": _iso(self.observed_at),
            "classification": self.classification.value,
        }


@dataclass(frozen=True)
class PriceSummary:
    target_id: str
    product_id: str | None
    listing_id: str | None
    mall_id: str
    external_product_id: str | None
    product_url: str
    product_name: str | None
    current_price: int | None
    previous_price: int | None
    price_change: int | None
    price_change_percent: float | None
    first_price: int | None
    lowest_price: int | None
    highest_price: int | None
    observed_at: datetime | None
    history_count: int
    classification: PriceChangeClassification
    has_price_observation: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "product_id": self.product_id,
            "listing_id": self.listing_id,
            "mall_id": self.mall_id,
            "external_product_id": self.external_product_id,
            "product_url": self.product_url,
            "product_name": self.product_name,
            "current_price": self.current_price,
            "previous_price": self.previous_price,
            "price_change": self.price_change,
            "price_change_percent": self.price_change_percent,
            "first_price": self.first_price,
            "lowest_price": self.lowest_price,
            "highest_price": self.highest_price,
            "observed_at": _iso(self.observed_at),
            "history_count": self.history_count,
            "classification": self.classification.value,
            "has_price_observation": self.has_price_observation,
        }


@dataclass(frozen=True)
class PriceHistoryEntryView:
    observed_at: datetime | None
    price: int | None
    previous_price: int | None
    price_change: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed_at": _iso(self.observed_at),
            "price": self.price,
            "previous_price": self.previous_price,
            "price_change": self.price_change,
        }


@dataclass(frozen=True)
class GpuPriceStatusSummary:
    targets: int
    with_price: int
    without_price: int
    price_down: int
    price_up: int
    unchanged: int
    no_history: int
    invalid_price: int
    average_current_price: float | None
    lowest_current_price: int | None
    highest_current_price: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "targets": self.targets,
            "with_price": self.with_price,
            "without_price": self.without_price,
            "price_down": self.price_down,
            "price_up": self.price_up,
            "unchanged": self.unchanged,
            "no_history": self.no_history,
            "invalid_price": self.invalid_price,
            "average_current_price": self.average_current_price,
            "lowest_current_price": self.lowest_current_price,
            "highest_current_price": self.highest_current_price,
        }


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        from pricebrain_app.crawler.targets import utc_now

        value = value.replace(tzinfo=utc_now().tzinfo)
    return value.isoformat()
