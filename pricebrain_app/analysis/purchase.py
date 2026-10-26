"""Rule-based 구매 적정성 — PRD §13.

PRD §13 asks for explainable rules before any ML:
- 구매 고려: below the recent average and close to the recent low
- 관망: around the average
- 구매 비추천: above the recent average while the price is trending down
"""

from __future__ import annotations

from dataclasses import dataclass

from pricebrain_app.analysis.models import (
    PriceStats,
    PriceTrend,
    PurchaseAssessment,
    PurchaseVerdict,
)

TREND_WINDOW_DAYS = 7


@dataclass(frozen=True)
class PurchaseRules:
    """Thresholds in percent; defaults are a starting point, tune against real data."""

    below_average_rate: float = -3.0
    above_average_rate: float = 3.0
    near_min_rate: float = 3.0
    trend_rate: float = 1.0
    min_coverage_days: float = 3.0


DEFAULT_RULES = PurchaseRules()

VERDICT_LABELS = {
    PurchaseVerdict.BUY_CONSIDER: "구매 고려",
    PurchaseVerdict.WAIT: "관망",
    PurchaseVerdict.NOT_RECOMMENDED: "구매 비추천",
    PurchaseVerdict.INSUFFICIENT_DATA: "데이터 부족",
}


def classify_trend(trend_stats: PriceStats, rules: PurchaseRules = DEFAULT_RULES) -> PriceTrend:
    rate = trend_stats.price_change_rate
    if rate is None:
        return PriceTrend.UNKNOWN
    if rate <= -rules.trend_rate:
        return PriceTrend.DOWN
    if rate >= rules.trend_rate:
        return PriceTrend.UP
    return PriceTrend.FLAT


def _won(value: int) -> str:
    return f"{value:,}원"


def _describe(stats: PriceStats, trend: PriceTrend, trend_rate: float | None) -> list[str]:
    days = stats.window_days
    reasons: list[str] = []
    rate = stats.diff_from_average_rate
    if rate is not None:
        if rate < 0:
            reasons.append(f"현재 가격은 최근 {days}일 평균보다 {abs(rate):.1f}% 낮습니다.")
        elif rate > 0:
            reasons.append(f"현재 가격은 최근 {days}일 평균보다 {rate:.1f}% 높습니다.")
        else:
            reasons.append(f"현재 가격은 최근 {days}일 평균과 같습니다.")
    if stats.diff_from_min is not None:
        if stats.diff_from_min == 0:
            reasons.append(f"현재 가격이 최근 {days}일 최저가입니다.")
        else:
            reasons.append(
                f"현재 가격은 최근 {days}일 최저가와 {_won(stats.diff_from_min)} 차이입니다."
            )
    if trend is PriceTrend.DOWN and trend_rate is not None:
        reasons.append(f"최근 {TREND_WINDOW_DAYS}일 동안 가격이 {abs(trend_rate):.1f}% 내렸습니다.")
    elif trend is PriceTrend.UP and trend_rate is not None:
        reasons.append(f"최근 {TREND_WINDOW_DAYS}일 동안 가격이 {trend_rate:.1f}% 올랐습니다.")
    return reasons


def assess_purchase(
    stats: PriceStats,
    trend_stats: PriceStats,
    rules: PurchaseRules = DEFAULT_RULES,
) -> PurchaseAssessment:
    """Assess with window stats (usually 30일) plus a short trend window (7일)."""
    trend = classify_trend(trend_stats, rules)
    trend_rate = trend_stats.price_change_rate

    if not stats.has_data or stats.coverage_days < rules.min_coverage_days:
        verdict = PurchaseVerdict.INSUFFICIENT_DATA
        reasons = [f"가격 이력이 {rules.min_coverage_days:g}일 미만이라 판단하기 어렵습니다."]
        return PurchaseAssessment(
            verdict=verdict,
            label=VERDICT_LABELS[verdict],
            trend=trend,
            trend_change_rate=trend_rate,
            reasons=reasons,
        )

    vs_average = stats.diff_from_average_rate or 0.0
    near_min = (
        stats.min_price is not None
        and stats.current_price is not None
        and stats.current_price <= stats.min_price * (1 + rules.near_min_rate / 100)
    )

    if vs_average <= rules.below_average_rate and near_min:
        verdict = PurchaseVerdict.BUY_CONSIDER
    elif vs_average >= rules.above_average_rate and trend is PriceTrend.DOWN:
        verdict = PurchaseVerdict.NOT_RECOMMENDED
    else:
        verdict = PurchaseVerdict.WAIT

    return PurchaseAssessment(
        verdict=verdict,
        label=VERDICT_LABELS[verdict],
        trend=trend,
        trend_change_rate=trend_rate,
        reasons=_describe(stats, trend, trend_rate),
    )
