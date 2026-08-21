"""In-memory audit event history store — populated from runner cycles."""

from __future__ import annotations

import uuid
from collections import deque
from datetime import datetime
from threading import Lock
from typing import TYPE_CHECKING, Any

from pricebrain_app.crawler.audit_operations_models import (
    AuditEvent,
    AuditEventType,
    mall_id_from_target_id,
    parse_audit_event,
)
from pricebrain_app.crawler.notification_models import NotificationSendResult, NotificationSendStatus
from pricebrain_app.crawler.price_alert_models import AlertEvaluationOutcome, AlertEvaluationResult
from pricebrain_app.crawler.price_calculations import classify_price_change
from pricebrain_app.crawler.targets import utc_now

if TYPE_CHECKING:
    from pricebrain_app.crawler.price_alert_runner import PriceAlertRunnerCycleResult

_MAX_EVENTS = 500


class AuditEventStore:
    """Process-local append-only audit event history."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._events: deque[dict[str, Any]] = deque(maxlen=_MAX_EVENTS)

    def append(self, event: AuditEvent) -> None:
        with self._lock:
            self._events.appendleft(event.to_dict())

    def append_raw(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._events.appendleft(dict(payload))

    def list_raw(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._events)
        if limit is not None:
            return items[: max(int(limit), 0)]
        return items

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


_STORE = AuditEventStore()


def get_audit_event_store() -> AuditEventStore:
    return _STORE


def reset_audit_event_store() -> None:
    _STORE.clear()


def record_audit_events_from_cycle(
    cycle: PriceAlertRunnerCycleResult,
    *,
    results: list[AlertEvaluationResult] | None = None,
    notifications: list[NotificationSendResult] | None = None,
) -> None:
    store = get_audit_event_store()
    cycle_id = _cycle_id(cycle.cycle_started_at)
    runner_type = (
        AuditEventType.RUNNER_CYCLE_FAILED
        if cycle.errors or cycle.notification_failed > 0
        else AuditEventType.RUNNER_CYCLE_COMPLETED
    )
    duration = (cycle.cycle_finished_at - cycle.cycle_started_at).total_seconds()
    store.append(
        AuditEvent(
            event_id=_new_event_id(),
            event_type=runner_type,
            occurred_at=cycle.cycle_finished_at,
            runner_cycle_id=cycle_id,
            status=runner_type.value,
            message="; ".join(cycle.errors) if cycle.errors else None,
            metadata={
                "total_alerts": cycle.total_alerts,
                "evaluated": cycle.evaluated,
                "triggered": cycle.triggered,
                "skipped": cycle.skipped,
                "invalid": cycle.invalid,
                "notification_sent": cycle.notification_sent,
                "notification_failed": cycle.notification_failed,
                "duration_seconds": duration,
                "dry_run": cycle.dry_run,
            },
        )
    )

    if not results:
        return

    triggered = [item for item in results if item.outcome is AlertEvaluationOutcome.TRIGGERED]
    notification_pairs = list(zip(triggered, notifications or []))

    for result in results:
        event_type = _outcome_to_event_type(result.outcome)
        classification = _classification_for(result)
        store.append(
            AuditEvent(
                event_id=_new_event_id(),
                event_type=event_type,
                occurred_at=result.observed_at or cycle.cycle_finished_at,
                alert_id=result.alert_id,
                target_id=result.target_id,
                mall_id=mall_id_from_target_id(result.target_id),
                status=result.outcome.value,
                price=result.current_price,
                previous_price=result.previous_price,
                classification=classification,
                runner_cycle_id=cycle_id,
                message=result.message,
                metadata={"threshold": result.threshold, "alert_type": result.alert_type.value},
            )
        )

    for evaluation, notification in notification_pairs:
        store.append(
            AuditEvent(
                event_id=_new_event_id(),
                event_type=_notification_to_event_type(notification.status),
                occurred_at=cycle.cycle_finished_at,
                alert_id=evaluation.alert_id,
                target_id=evaluation.target_id,
                mall_id=mall_id_from_target_id(evaluation.target_id),
                channel=notification.channel.value,
                status=notification.status.value,
                price=evaluation.current_price,
                previous_price=evaluation.previous_price,
                classification=_classification_for(evaluation),
                runner_cycle_id=cycle_id,
                message=notification.message,
                metadata={"notification_id": notification.notification_id},
            )
        )


def _outcome_to_event_type(outcome: AlertEvaluationOutcome) -> AuditEventType:
    mapping = {
        AlertEvaluationOutcome.TRIGGERED: AuditEventType.ALERT_TRIGGERED,
        AlertEvaluationOutcome.SKIPPED: AuditEventType.ALERT_SKIPPED,
        AlertEvaluationOutcome.INVALID: AuditEventType.ALERT_INVALID,
        AlertEvaluationOutcome.NOT_TRIGGERED: AuditEventType.ALERT_EVALUATED,
    }
    return mapping.get(outcome, AuditEventType.UNKNOWN)


def _notification_to_event_type(status: NotificationSendStatus) -> AuditEventType:
    mapping = {
        NotificationSendStatus.SENT: AuditEventType.NOTIFICATION_SENT,
        NotificationSendStatus.FAILED: AuditEventType.NOTIFICATION_FAILED,
        NotificationSendStatus.SKIPPED: AuditEventType.NOTIFICATION_SKIPPED,
        NotificationSendStatus.UNSUPPORTED: AuditEventType.NOTIFICATION_SKIPPED,
    }
    return mapping.get(status, AuditEventType.UNKNOWN)


def _classification_for(result: AlertEvaluationResult) -> str | None:
    if result.current_price is None:
        return None
    has_history = result.previous_price is not None
    return classify_price_change(
        result.current_price,
        result.previous_price,
        has_history=has_history,
    ).value


def _cycle_id(started_at: datetime) -> str:
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=utc_now().tzinfo)
    return f"cycle-{int(started_at.timestamp())}"


def _new_event_id() -> str:
    return uuid.uuid4().hex


def load_audit_snapshots(
    store: AuditEventStore | None = None,
    *,
    limit: int | None = None,
) -> tuple[list[tuple[AuditEvent | None, str | None]], int]:
    """Parse raw events with per-event failure isolation."""
    raw_items = (store or get_audit_event_store()).list_raw(limit=limit)
    parsed: list[tuple[AuditEvent | None, str | None]] = []
    read_errors = 0
    for item in raw_items:
        event, error = parse_audit_event(item)
        if error is not None:
            read_errors += 1
            parsed.append((None, error))
        else:
            parsed.append((event, None))
    return parsed, read_errors
