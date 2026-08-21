"""Price alert evaluation and orchestration — no crawler or ingest writes."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pricebrain_app.crawler.logging_utils import get_crawler_logger
from pricebrain_app.crawler.price_alert_events import log_price_alert_event
from pricebrain_app.crawler.price_alert_models import (
    AlertEvaluationOutcome,
    AlertEvaluationResult,
    PriceAlert,
    PriceAlertType,
)
from pricebrain_app.crawler.price_alert_repository import PriceAlertRepository
from pricebrain_app.crawler.price_calculations import (
    calculate_price_change_percent,
    is_valid_price,
)
from pricebrain_app.crawler.price_ops_models import PriceChangeClassification, PriceSnapshot
from pricebrain_app.crawler.price_operations_view import PriceOperationsView
from pricebrain_app.crawler.targets import utc_now

logger = get_crawler_logger("crawler.price_alert")


@dataclass(frozen=True)
class AlertCheckSummary:
    total: int
    triggered: int
    not_triggered: int
    skipped: int
    invalid: int
    failed: int

    def to_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            "triggered": self.triggered,
            "not_triggered": self.not_triggered,
            "skipped": self.skipped,
            "invalid": self.invalid,
            "failed": self.failed,
        }


def evaluate_alert(
    alert: PriceAlert,
    snapshot: PriceSnapshot,
    *,
    now: datetime | None = None,
) -> AlertEvaluationResult:
    """Pure alert evaluation — no Firestore mutations."""
    run_at = now or utc_now()
    current = snapshot.price
    previous = snapshot.previous_price

    if not _snapshot_is_evaluable(snapshot):
        return AlertEvaluationResult(
            alert_id=alert.alert_id,
            target_id=alert.target_id,
            alert_type=alert.alert_type,
            outcome=AlertEvaluationOutcome.INVALID,
            current_price=current,
            previous_price=previous,
            threshold=alert.threshold,
            message="price observation unavailable",
            observed_at=snapshot.observed_at,
        )

    would_trigger, reason = _evaluate_condition(alert, current=current, previous=previous)
    if not would_trigger:
        return AlertEvaluationResult(
            alert_id=alert.alert_id,
            target_id=alert.target_id,
            alert_type=alert.alert_type,
            outcome=AlertEvaluationOutcome.NOT_TRIGGERED,
            current_price=current,
            previous_price=previous,
            threshold=alert.threshold,
            message=reason,
            observed_at=snapshot.observed_at,
        )

    if _is_duplicate_trigger(alert, current=current, now=run_at):
        return AlertEvaluationResult(
            alert_id=alert.alert_id,
            target_id=alert.target_id,
            alert_type=alert.alert_type,
            outcome=AlertEvaluationOutcome.SKIPPED,
            current_price=current,
            previous_price=previous,
            threshold=alert.threshold,
            message="duplicate trigger for same observed price",
            observed_at=snapshot.observed_at,
        )

    return AlertEvaluationResult(
        alert_id=alert.alert_id,
        target_id=alert.target_id,
        alert_type=alert.alert_type,
        outcome=AlertEvaluationOutcome.TRIGGERED,
        current_price=current,
        previous_price=previous,
        threshold=alert.threshold,
        message=reason,
        observed_at=snapshot.observed_at,
    )


class PriceAlertService:
    """Evaluate enabled alerts against latest price snapshots."""

    def __init__(
        self,
        alert_repository: PriceAlertRepository,
        price_operations_view: PriceOperationsView,
    ) -> None:
        self._alerts = alert_repository
        self._prices = price_operations_view

    def check_enabled_alerts(self, *, now: datetime | None = None) -> tuple[list[AlertEvaluationResult], AlertCheckSummary]:
        run_at = now or utc_now()
        enabled = self._alerts.list_enabled()
        results: list[AlertEvaluationResult] = []
        summary = AlertCheckSummary(
            total=len(enabled),
            triggered=0,
            not_triggered=0,
            skipped=0,
            invalid=0,
            failed=0,
        )

        for alert in enabled:
            try:
                snapshot = self._prices.get_current_price(alert.target_id)
                if snapshot is None:
                    result = AlertEvaluationResult(
                        alert_id=alert.alert_id,
                        target_id=alert.target_id,
                        alert_type=alert.alert_type,
                        outcome=AlertEvaluationOutcome.INVALID,
                        current_price=None,
                        previous_price=None,
                        threshold=alert.threshold,
                        message="target not found",
                    )
                    self._log_result(alert, result)
                    results.append(result)
                    summary = _increment_summary(summary, result.outcome)
                    continue

                alert = _reset_duplicate_state_if_price_changed(self._alerts, alert, snapshot)
                result = evaluate_alert(alert, snapshot, now=run_at)
                if result.outcome is AlertEvaluationOutcome.TRIGGERED and is_valid_price(result.current_price):
                    self._alerts.mark_triggered(
                        alert.alert_id,
                        observed_price=int(result.current_price),
                        triggered_at=run_at,
                    )
                self._log_result(alert, result, snapshot=snapshot)
                results.append(result)
                summary = _increment_summary(summary, result.outcome)
            except Exception as exc:
                summary = AlertCheckSummary(
                    total=summary.total,
                    triggered=summary.triggered,
                    not_triggered=summary.not_triggered,
                    skipped=summary.skipped,
                    invalid=summary.invalid,
                    failed=summary.failed + 1,
                )
                log_price_alert_event(
                    logger,
                    "price_alert.invalid",
                    alert_id=alert.alert_id,
                    target_id=alert.target_id,
                    mall_id=alert.mall_id,
                    alert_type=alert.alert_type.value,
                    outcome=AlertEvaluationOutcome.INVALID.value,
                    message=str(exc),
                )
        return results, summary

    def _log_result(
        self,
        alert: PriceAlert,
        result: AlertEvaluationResult,
        *,
        snapshot: PriceSnapshot | None = None,
    ) -> None:
        event = _event_for_outcome(result.outcome)
        log_price_alert_event(
            logger,
            event,
            alert_id=alert.alert_id,
            target_id=alert.target_id,
            mall_id=alert.mall_id,
            alert_type=alert.alert_type.value,
            outcome=result.outcome.value,
            current_price=result.current_price,
            previous_price=result.previous_price,
            threshold=result.threshold,
            message=result.message,
            product_url=snapshot.product_url if snapshot is not None else None,
        )


def _snapshot_is_evaluable(snapshot: PriceSnapshot) -> bool:
    if snapshot.classification in {
        PriceChangeClassification.NO_HISTORY,
        PriceChangeClassification.INVALID_PRICE,
    }:
        return False
    return is_valid_price(snapshot.price)


def _evaluate_condition(
    alert: PriceAlert,
    *,
    current: int,
    previous: int | None,
) -> tuple[bool, str]:
    alert_type = alert.alert_type
    threshold = alert.threshold

    if alert_type is PriceAlertType.PRICE_BELOW:
        triggered = current <= threshold
        return triggered, f"current {current:,} <= threshold {threshold:,.0f}"

    if alert_type is PriceAlertType.PRICE_DROP_PERCENT:
        if not is_valid_price(previous):
            return False, "previous price unavailable"
        drop_percent = calculate_price_change_percent(current, previous)
        if drop_percent is None or drop_percent >= 0:
            return False, "no price drop"
        drop_amount = abs(drop_percent)
        triggered = drop_amount >= threshold
        return triggered, f"drop {drop_amount:.2f}% >= threshold {threshold:.2f}%"

    if alert_type is PriceAlertType.PRICE_DROP_AMOUNT:
        if not is_valid_price(previous):
            return False, "previous price unavailable"
        drop_amount = int(previous) - int(current)
        if drop_amount <= 0:
            return False, f"drop amount {drop_amount:,} below threshold"
        triggered = drop_amount >= threshold
        return triggered, f"drop {drop_amount:,} >= threshold {threshold:,.0f}"

    if alert_type is PriceAlertType.PRICE_UP:
        if not is_valid_price(previous):
            return False, "previous price unavailable"
        triggered = current > previous
        return triggered, f"current {current:,} > previous {previous:,}"

    if alert_type is PriceAlertType.PRICE_CHANGED:
        if not is_valid_price(previous):
            return False, "previous price unavailable"
        triggered = current != previous
        return triggered, f"current {current:,} != previous {previous:,}"

    return False, "unsupported alert type"


def _is_duplicate_trigger(alert: PriceAlert, *, current: int, now: datetime) -> bool:
    if alert.last_triggered_at is None or alert.last_observed_price is None:
        return False
    if alert.last_observed_price != current:
        return False
    if alert.cooldown_seconds > 0:
        elapsed = (now - alert.last_triggered_at).total_seconds()
        if elapsed >= alert.cooldown_seconds:
            return False
    return True


def _reset_duplicate_state_if_price_changed(
    repository: PriceAlertRepository,
    alert: PriceAlert,
    snapshot: PriceSnapshot,
) -> PriceAlert:
    if not is_valid_price(snapshot.price):
        return alert
    if alert.last_observed_price is None:
        return alert
    if snapshot.price == alert.last_observed_price:
        return alert
    return repository.update(alert.alert_id, last_observed_price=None)


def _event_for_outcome(outcome: AlertEvaluationOutcome) -> str:
    if outcome is AlertEvaluationOutcome.TRIGGERED:
        return "price_alert.triggered"
    if outcome is AlertEvaluationOutcome.SKIPPED:
        return "price_alert.skipped"
    if outcome is AlertEvaluationOutcome.INVALID:
        return "price_alert.invalid"
    return "price_alert.evaluated"


def _increment_summary(summary: AlertCheckSummary, outcome: AlertEvaluationOutcome) -> AlertCheckSummary:
    return AlertCheckSummary(
        total=summary.total,
        triggered=summary.triggered + (1 if outcome is AlertEvaluationOutcome.TRIGGERED else 0),
        not_triggered=summary.not_triggered + (1 if outcome is AlertEvaluationOutcome.NOT_TRIGGERED else 0),
        skipped=summary.skipped + (1 if outcome is AlertEvaluationOutcome.SKIPPED else 0),
        invalid=summary.invalid + (1 if outcome is AlertEvaluationOutcome.INVALID else 0),
        failed=summary.failed,
    )
