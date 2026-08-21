"""Read-only audit event history DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pricebrain_app.crawler.targets import parse_datetime, utc_now


class AuditEventType(str, Enum):
    ALERT_EVALUATED = "ALERT_EVALUATED"
    ALERT_TRIGGERED = "ALERT_TRIGGERED"
    ALERT_SKIPPED = "ALERT_SKIPPED"
    ALERT_INVALID = "ALERT_INVALID"
    ALERT_CREATED = "ALERT_CREATED"
    NOTIFICATION_SENT = "NOTIFICATION_SENT"
    NOTIFICATION_FAILED = "NOTIFICATION_FAILED"
    NOTIFICATION_SKIPPED = "NOTIFICATION_SKIPPED"
    RUNNER_CYCLE_COMPLETED = "RUNNER_CYCLE_COMPLETED"
    RUNNER_CYCLE_FAILED = "RUNNER_CYCLE_FAILED"
    REMEDIATION_PLANNED = "REMEDIATION_PLANNED"
    REMEDIATION_APPROVAL_BLOCKED = "REMEDIATION_APPROVAL_BLOCKED"
    REMEDIATION_DRY_RUN = "REMEDIATION_DRY_RUN"
    REMEDIATION_EXECUTED = "REMEDIATION_EXECUTED"
    REMEDIATION_FAILED = "REMEDIATION_FAILED"
    UNKNOWN = "UNKNOWN"


RUNNER_EVENT_TYPES = frozenset(
    {
        AuditEventType.RUNNER_CYCLE_COMPLETED,
        AuditEventType.RUNNER_CYCLE_FAILED,
    }
)

NOTIFICATION_EVENT_TYPES = frozenset(
    {
        AuditEventType.NOTIFICATION_SENT,
        AuditEventType.NOTIFICATION_FAILED,
        AuditEventType.NOTIFICATION_SKIPPED,
    }
)

ALERT_EVENT_TYPES = frozenset(
    {
        AuditEventType.ALERT_EVALUATED,
        AuditEventType.ALERT_TRIGGERED,
        AuditEventType.ALERT_SKIPPED,
        AuditEventType.ALERT_INVALID,
        AuditEventType.ALERT_CREATED,
    }
)


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    event_type: AuditEventType
    occurred_at: datetime
    alert_id: str | None = None
    target_id: str | None = None
    mall_id: str | None = None
    channel: str | None = None
    status: str | None = None
    price: int | None = None
    previous_price: int | None = None
    classification: str | None = None
    runner_cycle_id: str | None = None
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "occurred_at": _iso(self.occurred_at),
            "alert_id": self.alert_id,
            "target_id": self.target_id,
            "mall_id": self.mall_id,
            "channel": self.channel,
            "status": self.status,
            "price": self.price,
            "previous_price": self.previous_price,
            "classification": self.classification,
            "runner_cycle_id": self.runner_cycle_id,
            "message": self.message,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class AuditEventSnapshot:
    event: AuditEvent | None
    summary: str
    read_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"summary": self.summary}
        if self.event is not None:
            payload["event"] = self.event.to_dict()
        if self.read_error is not None:
            payload["read_error"] = self.read_error
        return payload


@dataclass(frozen=True)
class AuditEventSummary:
    total: int
    recent: int
    by_type: tuple[tuple[str, int], ...]
    by_status: tuple[tuple[str, int], ...]
    by_channel: tuple[tuple[str, int], ...]
    alert_events: int
    notification_events: int
    runner_events: int
    read_errors: int

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "total": self.total,
            "recent": self.recent,
            "by_type": {key: value for key, value in self.by_type},
            "by_status": {key: value for key, value in self.by_status},
            "by_channel": {key: value for key, value in self.by_channel},
            "alert_events": self.alert_events,
            "notification_events": self.notification_events,
            "runner_events": self.runner_events,
            "read_errors": self.read_errors,
        }
        failure_events = sum(
            count
            for event_type, count in self.by_type
            if any(marker in event_type.upper() for marker in ("FAILED", "INVALID", "BLOCKED"))
        )
        payload["failure_events"] = failure_events
        return payload


class AuditHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class AuditOperationsSnapshot:
    generated_at: datetime
    summary: AuditEventSummary
    health: AuditHealthStatus
    health_reasons: tuple[str, ...]
    events: tuple[AuditEventSnapshot, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": _iso(self.generated_at),
            "summary": self.summary.to_dict(),
            "health": self.health.value,
            "health_reasons": list(self.health_reasons),
            "events": [item.to_dict() for item in self.events],
        }


@dataclass(frozen=True)
class AuditEventFilter:
    event_type: str | None = None
    alert_id: str | None = None
    target_id: str | None = None
    mall_id: str | None = None
    status: str | None = None
    channel: str | None = None
    failures_only: bool = False
    runner_only: bool = False
    since: datetime | None = None
    until: datetime | None = None
    recent: int | None = None


def parse_audit_event_type(value: str | None) -> AuditEventType:
    if value is None:
        return AuditEventType.UNKNOWN
    text = str(value).strip().upper().replace("-", "_")
    try:
        return AuditEventType(text)
    except ValueError:
        return AuditEventType.UNKNOWN


def parse_audit_event(data: dict[str, Any]) -> tuple[AuditEvent | None, str | None]:
    try:
        event_id = str(data.get("event_id") or "").strip()
        if not event_id:
            return None, "missing event_id"
        occurred_raw = data.get("occurred_at")
        occurred_at = parse_datetime(occurred_raw)
        if occurred_at is None:
            occurred_at = utc_now()
        event_type = parse_audit_event_type(data.get("event_type"))
        metadata = data.get("metadata")
        return (
            AuditEvent(
                event_id=event_id,
                event_type=event_type,
                occurred_at=occurred_at,
                alert_id=_optional_str(data.get("alert_id")),
                target_id=_optional_str(data.get("target_id")),
                mall_id=_optional_str(data.get("mall_id")),
                channel=_optional_str(data.get("channel")),
                status=_optional_str(data.get("status")),
                price=_optional_int(data.get("price")),
                previous_price=_optional_int(data.get("previous_price")),
                classification=_optional_str(data.get("classification")),
                runner_cycle_id=_optional_str(data.get("runner_cycle_id")),
                message=_optional_str(data.get("message")),
                metadata=dict(metadata) if isinstance(metadata, dict) else {},
            ),
            None,
        )
    except Exception as exc:
        return None, str(exc)


def mall_id_from_target_id(target_id: str | None) -> str | None:
    if not target_id:
        return None
    parts = target_id.split("_", 1)
    return parts[0].lower() if parts else None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=utc_now().tzinfo)
    return value.isoformat()
