"""In-memory read-only health history for alert runner and notifications."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import TYPE_CHECKING, Any

from pricebrain_app.crawler.notification_models import NotificationSendResult, NotificationSendStatus
from pricebrain_app.crawler.price_alert_models import AlertEvaluationOutcome, AlertEvaluationResult

if TYPE_CHECKING:
    from pricebrain_app.crawler.price_alert_runner import PriceAlertRunnerCycleResult

_MAX_CYCLES = 50
_MAX_NOTIFICATIONS = 100


@dataclass(frozen=True)
class RecordedNotificationEvent:
    notification_id: str
    alert_id: str
    target_id: str
    channel: str
    status: str
    message: str
    recorded_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "alert_id": self.alert_id,
            "target_id": self.target_id,
            "channel": self.channel,
            "status": self.status,
            "message": self.message,
            "recorded_at": self.recorded_at.isoformat(),
        }


class AlertOpsHealthStore:
    """Process-local store for runner cycles and notification outcomes."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._cycles: deque[Any] = deque(maxlen=_MAX_CYCLES)
        self._notifications: deque[RecordedNotificationEvent] = deque(maxlen=_MAX_NOTIFICATIONS)

    def record_cycle(
        self,
        cycle: PriceAlertRunnerCycleResult,
        *,
        results: list[AlertEvaluationResult] | None = None,
        notifications: list[NotificationSendResult] | None = None,
    ) -> None:
        with self._lock:
            self._cycles.appendleft(cycle)
            if results and notifications:
                triggered = [item for item in results if item.outcome is AlertEvaluationOutcome.TRIGGERED]
                for evaluation, notification in zip(triggered, notifications):
                    self._notifications.appendleft(
                        RecordedNotificationEvent(
                            notification_id=notification.notification_id,
                            alert_id=evaluation.alert_id,
                            target_id=evaluation.target_id,
                            channel=notification.channel.value,
                            status=notification.status.value,
                            message=notification.message,
                            recorded_at=cycle.cycle_finished_at,
                        )
                    )

    def list_cycles(self, *, limit: int | None = None) -> list[Any]:
        with self._lock:
            items = list(self._cycles)
        if limit is not None:
            return items[: max(int(limit), 0)]
        return items

    def list_notifications(self, *, limit: int | None = None) -> list[RecordedNotificationEvent]:
        with self._lock:
            items = list(self._notifications)
        if limit is not None:
            return items[: max(int(limit), 0)]
        return items

    def clear(self) -> None:
        with self._lock:
            self._cycles.clear()
            self._notifications.clear()


_STORE = AlertOpsHealthStore()


def get_alert_ops_health_store() -> AlertOpsHealthStore:
    return _STORE


def reset_alert_ops_health_store() -> None:
    _STORE.clear()
    from pricebrain_app.crawler.audit_event_store import reset_audit_event_store
    from pricebrain_app.crawler.execution_history_store import reset_execution_history_store

    reset_audit_event_store()
    reset_execution_history_store()


def record_alert_ops_cycle(
    cycle: PriceAlertRunnerCycleResult,
    *,
    results: list[AlertEvaluationResult] | None = None,
    notifications: list[NotificationSendResult] | None = None,
) -> None:
    get_alert_ops_health_store().record_cycle(
        cycle,
        results=results,
        notifications=notifications,
    )
    from pricebrain_app.crawler.audit_event_store import record_audit_events_from_cycle

    record_audit_events_from_cycle(
        cycle,
        results=results,
        notifications=notifications,
    )
