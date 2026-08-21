"""Pure audit event health classification — no I/O."""

from __future__ import annotations

from pricebrain_app.crawler.audit_operations_models import AuditEventSummary, AuditHealthStatus

_FAILURE_TYPE_MARKERS = ("FAILED", "INVALID", "BLOCKED")


def _failure_event_count(summary: AuditEventSummary) -> int:
    total = 0
    for event_type, count in summary.by_type:
        normalized = event_type.upper()
        if any(marker in normalized for marker in _FAILURE_TYPE_MARKERS):
            total += count
    return total


def classify_audit_health(summary: AuditEventSummary) -> tuple[AuditHealthStatus, tuple[str, ...]]:
    failure_events = _failure_event_count(summary)
    if summary.total == 0 and summary.read_errors == 0:
        return AuditHealthStatus.UNKNOWN, ("no audit events",)

    reasons: list[str] = []

    if summary.read_errors >= 3:
        reasons.append(f"{summary.read_errors} audit read errors")
        return AuditHealthStatus.CRITICAL, tuple(reasons)

    if failure_events >= 3:
        reasons.append("repeated audit failures")
        return AuditHealthStatus.CRITICAL, tuple(reasons)

    if failure_events >= 1:
        reasons.append("recent audit failures")
    if summary.read_errors >= 1:
        reasons.append(f"{summary.read_errors} audit read errors")

    if reasons:
        return AuditHealthStatus.DEGRADED, tuple(reasons)

    if summary.total == 0:
        return AuditHealthStatus.UNKNOWN, ("no audit events",)

    return AuditHealthStatus.HEALTHY, ()
