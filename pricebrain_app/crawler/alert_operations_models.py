"""Read-only alert and notification operations DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pricebrain_app.crawler.targets import utc_now


@dataclass(frozen=True)
class AlertSummary:
    total: int
    enabled: int
    disabled: int
    triggered_recently: int
    never_triggered: int
    invalid: int
    by_type: tuple[tuple[str, int], ...]
    by_mall: tuple[tuple[str, int], ...]
    by_category: tuple[tuple[str, int], ...]
    read_errors: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "enabled": self.enabled,
            "disabled": self.disabled,
            "triggered_recently": self.triggered_recently,
            "never_triggered": self.never_triggered,
            "invalid": self.invalid,
            "by_type": {key: value for key, value in self.by_type},
            "by_mall": {key: value for key, value in self.by_mall},
            "by_category": {key: value for key, value in self.by_category},
            "read_errors": self.read_errors,
        }


@dataclass(frozen=True)
class AlertSnapshot:
    alert_id: str
    target_id: str
    mall_id: str
    alert_type: str
    threshold: float
    enabled: bool
    current_price: int | None
    previous_price: int | None
    classification: str | None
    last_observed_price: int | None
    last_triggered_at: datetime | None
    cooldown_seconds: int
    brand: str | None
    product_name: str | None
    category: str | None = None
    read_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "target_id": self.target_id,
            "mall_id": self.mall_id,
            "alert_type": self.alert_type,
            "threshold": self.threshold,
            "enabled": self.enabled,
            "current_price": self.current_price,
            "previous_price": self.previous_price,
            "classification": self.classification,
            "last_observed_price": self.last_observed_price,
            "last_triggered_at": _iso(self.last_triggered_at),
            "cooldown_seconds": self.cooldown_seconds,
            "brand": self.brand,
            "product_name": self.product_name,
            "category": self.category,
            "read_error": self.read_error,
        }


@dataclass(frozen=True)
class NotificationOpsSummary:
    total_evaluated: int
    notification_sent: int
    notification_failed: int
    notification_skipped: int
    by_channel: tuple[tuple[str, int], ...]
    recent_failures: tuple[dict[str, Any], ...]
    recent_events: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_evaluated": self.total_evaluated,
            "notification_sent": self.notification_sent,
            "notification_failed": self.notification_failed,
            "notification_skipped": self.notification_skipped,
            "by_channel": {key: value for key, value in self.by_channel},
            "recent_events": list(self.recent_events),
            "recent_failures": list(self.recent_failures),
        }


@dataclass(frozen=True)
class RunnerHealthView:
    last_cycle_started_at: datetime | None
    last_cycle_finished_at: datetime | None
    duration_seconds: float | None
    total_alerts: int
    evaluated: int
    triggered: int
    skipped: int
    invalid: int
    notification_sent: int
    notification_failed: int
    errors: tuple[str, ...]
    last_successful_cycle_at: datetime | None
    last_failed_cycle_at: datetime | None
    recent_cycles: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_cycle_started_at": _iso(self.last_cycle_started_at),
            "last_cycle_finished_at": _iso(self.last_cycle_finished_at),
            "duration_seconds": self.duration_seconds,
            "total_alerts": self.total_alerts,
            "evaluated": self.evaluated,
            "triggered": self.triggered,
            "skipped": self.skipped,
            "invalid": self.invalid,
            "notification_sent": self.notification_sent,
            "notification_failed": self.notification_failed,
            "errors": list(self.errors),
            "last_successful_cycle_at": _iso(self.last_successful_cycle_at),
            "last_failed_cycle_at": _iso(self.last_failed_cycle_at),
            "recent_cycles": list(self.recent_cycles),
        }


@dataclass(frozen=True)
class AlertListFilter:
    enabled: bool | None = None
    alert_type: str | None = None
    mall_id: str | None = None
    target_id: str | None = None
    category: str | None = None


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=utc_now().tzinfo)
    return value.isoformat()
