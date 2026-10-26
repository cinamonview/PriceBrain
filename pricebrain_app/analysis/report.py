"""Plain-text report and threshold sensitivity over product analyses.

Used to eyeball verdicts on real data and to see how purchase-rule thresholds
shift them, before changing PurchaseRules defaults.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime

from pricebrain_app.analysis.models import PricePoint, ProductPriceAnalysis, PurchaseVerdict
from pricebrain_app.analysis.price_stats import compute_price_stats
from pricebrain_app.analysis.purchase import (
    DEFAULT_RULES,
    TREND_WINDOW_DAYS,
    PurchaseRules,
    assess_purchase,
)

DEFAULT_BELOW_AVERAGE_RATES = (-2.0, -3.0, -5.0)
DEFAULT_NEAR_MIN_RATES = (2.0, 3.0, 5.0)

_VERDICT_ORDER = (
    PurchaseVerdict.BUY_CONSIDER,
    PurchaseVerdict.WAIT,
    PurchaseVerdict.NOT_RECOMMENDED,
    PurchaseVerdict.INSUFFICIENT_DATA,
)


@dataclass(frozen=True)
class SensitivityRow:
    below_average_rate: float
    near_min_rate: float
    counts: dict[PurchaseVerdict, int]


def reassess(
    analysis: ProductPriceAnalysis, rules: PurchaseRules, *, now: datetime
) -> PurchaseVerdict:
    """Re-run the purchase rules on an existing analysis with different thresholds."""
    series = [PricePoint(crawled_at=p.crawled_at, price=p.price) for p in analysis.lowest_price_series]
    trend_stats = compute_price_stats(series, window_days=TREND_WINDOW_DAYS, now=now)
    return assess_purchase(analysis.stats, trend_stats, rules).verdict


def sensitivity(
    analyses: Sequence[ProductPriceAnalysis],
    *,
    now: datetime,
    below_average_rates: Sequence[float] = DEFAULT_BELOW_AVERAGE_RATES,
    near_min_rates: Sequence[float] = DEFAULT_NEAR_MIN_RATES,
    base: PurchaseRules = DEFAULT_RULES,
) -> list[SensitivityRow]:
    rows: list[SensitivityRow] = []
    for below in below_average_rates:
        for near in near_min_rates:
            rules = replace(base, below_average_rate=below, near_min_rate=near)
            counter = Counter(reassess(item, rules, now=now) for item in analyses)
            rows.append(
                SensitivityRow(
                    below_average_rate=below,
                    near_min_rate=near,
                    counts={verdict: counter.get(verdict, 0) for verdict in _VERDICT_ORDER},
                )
            )
    return rows


def _won(value: int | None) -> str:
    return "-" if value is None else f"{value:,}"


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:+.1f}%"


def format_report(analyses: Sequence[ProductPriceAnalysis]) -> str:
    if not analyses:
        return "분석할 상품이 없습니다."
    header = (
        f"{'상품':<34} {'현재가':>11} {'평균가':>11} {'최저가':>11} "
        f"{'평균대비':>8} {'변동':>8} {'이력(일)':>8}  판정"
    )
    lines = [header, "-" * len(header)]
    for item in analyses:
        stats = item.stats
        name = (item.product_name or item.product_id)[:34]
        lines.append(
            f"{name:<34} {_won(stats.current_price):>11} {_won(stats.average_price):>11} "
            f"{_won(stats.min_price):>11} {_pct(stats.diff_from_average_rate):>8} "
            f"{_pct(stats.price_change_rate):>8} {stats.coverage_days:>8.1f}  {item.purchase.label}"
        )
    counter = Counter(item.purchase.verdict for item in analyses)
    summary = ", ".join(f"{verdict.value} {counter.get(verdict, 0)}" for verdict in _VERDICT_ORDER)
    lines.extend(["", f"상품 {len(analyses)}개: {summary}"])
    return "\n".join(lines)


def format_sensitivity(rows: Sequence[SensitivityRow], *, total: int) -> str:
    lines = [
        f"판정 기준 민감도 (상품 {total}개) — 평균 대비 / 최저가 근접 임계값별 판정 수",
        f"{'평균대비<=':>10} {'최저가이내':>10} {'구매고려':>8} {'관망':>6} {'비추천':>6} {'데이터부족':>8}",
    ]
    for row in rows:
        counts = row.counts
        lines.append(
            f"{row.below_average_rate:>9.1f}% {row.near_min_rate:>9.1f}% "
            f"{counts[PurchaseVerdict.BUY_CONSIDER]:>8} {counts[PurchaseVerdict.WAIT]:>6} "
            f"{counts[PurchaseVerdict.NOT_RECOMMENDED]:>6} {counts[PurchaseVerdict.INSUFFICIENT_DATA]:>8}"
        )
    return "\n".join(lines)
