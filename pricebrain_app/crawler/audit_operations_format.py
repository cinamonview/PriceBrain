"""Human-readable audit event formatting."""

from __future__ import annotations

from datetime import datetime

from pricebrain_app.crawler.audit_operations_models import AuditEvent, AuditEventSnapshot, AuditEventType
from pricebrain_app.crawler.targets import utc_now


def format_audit_timestamp(value: datetime | None) -> str:
    if value is None:
        return "-"
    if value.tzinfo is None:
        value = value.replace(tzinfo=utc_now().tzinfo)
    return value.strftime("%Y-%m-%d %H:%M:%S")


def format_audit_event_summary(event: AuditEvent) -> str:
    event_type = event.event_type.value
    if event_type in {
        AuditEventType.ALERT_EVALUATED.value,
        AuditEventType.ALERT_TRIGGERED.value,
        AuditEventType.ALERT_SKIPPED.value,
        AuditEventType.ALERT_INVALID.value,
        AuditEventType.ALERT_CREATED.value,
    }:
        parts = [
            f"alert={event.alert_id or '-'}",
            f"target={event.target_id or '-'}",
        ]
        if event.price is not None:
            parts.append(f"price={event.price:,}")
        if event.classification:
            parts.append(f"classification={event.classification}")
        if event.status:
            parts.append(f"status={event.status}")
        return " ".join(parts)

    if event_type in {
        AuditEventType.NOTIFICATION_SENT.value,
        AuditEventType.NOTIFICATION_FAILED.value,
        AuditEventType.NOTIFICATION_SKIPPED.value,
    }:
        return " ".join(
            [
                f"alert={event.alert_id or '-'}",
                f"channel={event.channel or '-'}",
                f"status={event.status or '-'}",
            ]
        )

    if event_type in {
        AuditEventType.RUNNER_CYCLE_COMPLETED.value,
        AuditEventType.RUNNER_CYCLE_FAILED.value,
    }:
        evaluated = event.metadata.get("evaluated", "-")
        triggered = event.metadata.get("triggered", "-")
        failed = event.metadata.get("notification_failed", "-")
        duration = event.metadata.get("duration_seconds")
        duration_text = f"{duration:.2f}s" if isinstance(duration, (int, float)) else "-"
        return " ".join(
            [
                f"cycle={event.runner_cycle_id or '-'}",
                f"evaluated={evaluated}",
                f"triggered={triggered}",
                f"failed={failed}",
                f"duration={duration_text}",
            ]
        )

    return event.message or "-"


def format_audit_event_line(snapshot: AuditEventSnapshot) -> str:
    if snapshot.read_error is not None:
        return f"[invalid event] read_error={snapshot.read_error}"
    if snapshot.event is None:
        return "[invalid event]"
    event = snapshot.event
    return f"[{format_audit_timestamp(event.occurred_at)}] {event.event_type.value}\n{snapshot.summary}"


def format_audit_event_list(snapshots: list[AuditEventSnapshot], *, title: str) -> str:
    if not snapshots:
        return f"{title}\n\nNo audit events found."
    lines = [title, ""]
    for item in snapshots:
        lines.append(format_audit_event_line(item))
        lines.append("")
    return "\n".join(lines).rstrip()


def format_audit_lifecycle(snapshots: list[AuditEventSnapshot]) -> str:
    if not snapshots:
        return "No audit events found for this scope."
    lines: list[str] = []
    for index, item in enumerate(snapshots):
        if item.event is None:
            lines.append(f"INVALID EVENT ({item.read_error or 'unknown'})")
        else:
            lines.append(item.event.event_type.value.replace("_", " "))
        if index < len(snapshots) - 1:
            lines.append("↓")
    return "\n".join(lines)
