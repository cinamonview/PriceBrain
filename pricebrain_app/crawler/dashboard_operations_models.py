"""Read-only operations dashboard DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pricebrain_app.crawler.targets import utc_now


class DashboardHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class DashboardFilter:
    mall_id: str | None = None
    category: str | None = "gpu"
    tag: str | None = None
    recent: int = 10
    failures_only: bool = False


@dataclass(frozen=True)
class CrawlerDashboardSummary:
    total_targets: int = 0
    enabled_targets: int = 0
    disabled_targets: int = 0
    failed_targets: int = 0
    ssg_access_denied: int = 0
    high_priority_failed: int = 0
    recent_successes: int = 0
    recent_failures: int = 0
    by_mall: tuple[tuple[str, int], ...] = ()
    recent_failure_targets: tuple[dict[str, Any], ...] = ()
    read_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_targets": self.total_targets,
            "enabled_targets": self.enabled_targets,
            "disabled_targets": self.disabled_targets,
            "failed_targets": self.failed_targets,
            "ssg_access_denied": self.ssg_access_denied,
            "high_priority_failed": self.high_priority_failed,
            "recent_successes": self.recent_successes,
            "recent_failures": self.recent_failures,
            "by_mall": {key: value for key, value in self.by_mall},
            "recent_failure_targets": list(self.recent_failure_targets),
            "read_error": self.read_error,
        }


@dataclass(frozen=True)
class PriceDashboardSummary:
    targets: int = 0
    with_price: int = 0
    without_price: int = 0
    price_down: int = 0
    price_up: int = 0
    unchanged: int = 0
    no_history: int = 0
    invalid_price: int = 0
    read_error: str | None = None

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
            "read_error": self.read_error,
        }


@dataclass(frozen=True)
class AlertDashboardSummary:
    total: int = 0
    enabled: int = 0
    disabled: int = 0
    triggered_recently: int = 0
    never_triggered: int = 0
    invalid: int = 0
    by_type: tuple[tuple[str, int], ...] = ()
    recent_invalid: int = 0
    read_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "enabled": self.enabled,
            "disabled": self.disabled,
            "triggered_recently": self.triggered_recently,
            "never_triggered": self.never_triggered,
            "invalid": self.invalid,
            "by_type": {key: value for key, value in self.by_type},
            "recent_invalid": self.recent_invalid,
            "read_error": self.read_error,
        }


@dataclass(frozen=True)
class NotificationDashboardSummary:
    sent: int = 0
    failed: int = 0
    skipped: int = 0
    by_channel: tuple[tuple[str, int], ...] = ()
    recent_failures: tuple[dict[str, Any], ...] = ()
    read_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sent": self.sent,
            "failed": self.failed,
            "skipped": self.skipped,
            "by_channel": {key: value for key, value in self.by_channel},
            "recent_failures": list(self.recent_failures),
            "read_error": self.read_error,
        }


@dataclass(frozen=True)
class RunnerDashboardSummary:
    last_cycle_status: str = "UNKNOWN"
    last_run_at: datetime | None = None
    duration_seconds: float | None = None
    total_alerts: int = 0
    evaluated: int = 0
    triggered: int = 0
    notification_sent: int = 0
    notification_failed: int = 0
    last_successful_cycle_at: datetime | None = None
    last_failed_cycle_at: datetime | None = None
    recent_cycles: int = 0
    recent_failed_cycles: int = 0
    read_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_cycle_status": self.last_cycle_status,
            "last_run_at": _iso(self.last_run_at),
            "duration_seconds": self.duration_seconds,
            "total_alerts": self.total_alerts,
            "evaluated": self.evaluated,
            "triggered": self.triggered,
            "notification_sent": self.notification_sent,
            "notification_failed": self.notification_failed,
            "last_successful_cycle_at": _iso(self.last_successful_cycle_at),
            "last_failed_cycle_at": _iso(self.last_failed_cycle_at),
            "recent_cycles": self.recent_cycles,
            "recent_failed_cycles": self.recent_failed_cycles,
            "read_error": self.read_error,
        }


@dataclass(frozen=True)
class AuditDashboardSummary:
    recent_events: int = 0
    recent_failures: int = 0
    recent_alert_triggered: int = 0
    recent_notification_failed: int = 0
    recent_runner_failed: int = 0
    event_snapshots: tuple[dict[str, Any], ...] = ()
    read_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "recent_events": self.recent_events,
            "recent_failures": self.recent_failures,
            "recent_alert_triggered": self.recent_alert_triggered,
            "recent_notification_failed": self.recent_notification_failed,
            "recent_runner_failed": self.recent_runner_failed,
            "event_snapshots": list(self.event_snapshots),
            "read_error": self.read_error,
        }


@dataclass(frozen=True)
class DashboardSummary:
    health: DashboardHealthStatus
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "health": self.health.value,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class PriceBrainDashboardSnapshot:
    generated_at: datetime
    summary: DashboardSummary
    crawler: CrawlerDashboardSummary
    price: PriceDashboardSummary
    alerts: AlertDashboardSummary
    notifications: NotificationDashboardSummary
    runner: RunnerDashboardSummary
    audit: AuditDashboardSummary

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": _iso(self.generated_at),
            "summary": self.summary.to_dict(),
            "crawler": self.crawler.to_dict(),
            "price": self.price.to_dict(),
            "alerts": self.alerts.to_dict(),
            "notifications": self.notifications.to_dict(),
            "runner": self.runner.to_dict(),
            "audit": self.audit.to_dict(),
        }


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=utc_now().tzinfo)
    return value.isoformat()
