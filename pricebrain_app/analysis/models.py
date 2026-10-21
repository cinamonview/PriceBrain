"""Price analysis result models — PRD §14 가격 분석 지표."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

SUPPORTED_WINDOW_DAYS = (7, 30, 90)
DEFAULT_WINDOW_DAYS = 30


@dataclass(frozen=True)
class PricePoint:
    """One price_history document: the price that holds from crawled_at onward."""

    crawled_at: datetime
    price: int


class PriceTrend(str, Enum):
    DOWN = "DOWN"
    FLAT = "FLAT"
    UP = "UP"
    UNKNOWN = "UNKNOWN"


class PurchaseVerdict(str, Enum):
    BUY_CONSIDER = "BUY_CONSIDER"  # 구매 고려
    WAIT = "WAIT"  # 관망
    NOT_RECOMMENDED = "NOT_RECOMMENDED"  # 구매 비추천
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class PriceStats:
    """Window statistics over a step price series (PRD §11.1, §11.2, §14)."""

    window_days: int
    window_start: datetime
    window_end: datetime
    observed_from: datetime | None
    coverage_days: float
    data_points: int
    current_price: int | None
    min_price: int | None
    max_price: int | None
    average_price: int | None
    median_price: int | None
    price_range: int | None
    start_price: int | None
    price_change: int | None
    price_change_rate: float | None
    price_percentile: float | None
    diff_from_min: int | None
    diff_from_average_rate: float | None

    @property
    def has_data(self) -> bool:
        return self.current_price is not None


@dataclass(frozen=True)
class PurchaseAssessment:
    """Rule-based 구매 적정성 (PRD §13) with human-readable reasons."""

    verdict: PurchaseVerdict
    label: str
    trend: PriceTrend
    trend_change_rate: float | None
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ListingPriceAnalysis:
    """판매처 분석 (PRD §11.3) for one listing."""

    listing_id: str
    mall_id: str | None
    seller_id: str | None
    product_url: str | None
    available: bool
    stats: PriceStats


@dataclass(frozen=True)
class SeriesPoint:
    crawled_at: datetime
    price: int


@dataclass(frozen=True)
class ProductPriceAnalysis:
    product_id: str
    product_name: str | None
    window_days: int
    generated_at: datetime
    lowest_listing_id: str | None
    stats: PriceStats
    purchase: PurchaseAssessment
    listings: list[ListingPriceAnalysis]
    lowest_price_series: list[SeriesPoint]
