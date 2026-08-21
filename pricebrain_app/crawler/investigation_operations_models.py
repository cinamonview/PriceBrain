"""Read-only dashboard investigation DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pricebrain_app.crawler.dashboard_operations_models import (
    AlertDashboardSummary,
    AuditDashboardSummary,
    CrawlerDashboardSummary,
    DashboardHealthStatus,
    DashboardSummary,
    NotificationDashboardSummary,
    PriceDashboardSummary,
    RunnerDashboardSummary,
)
from pricebrain_app.crawler.targets import utc_now


class InvestigationSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


SEVERITY_ORDER = {
    InvestigationSeverity.CRITICAL: 4,
    InvestigationSeverity.ERROR: 3,
    InvestigationSeverity.WARNING: 2,
    InvestigationSeverity.INFO: 1,
}


@dataclass(frozen=True)
class InvestigationFinding:
    finding_id: str
    severity: InvestigationSeverity
    area: str
    code: str
    title: str
    message: str
    target_id: str | None = None
    alert_id: str | None = None
    event_id: str | None = None
    occurred_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "severity": self.severity.value,
            "area": self.area,
            "code": self.code,
            "title": self.title,
            "message": self.message,
            "target_id": self.target_id,
            "alert_id": self.alert_id,
            "event_id": self.event_id,
            "occurred_at": _iso(self.occurred_at),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class InvestigationSummary:
    total_findings: int
    info_count: int
    warning_count: int
    error_count: int
    critical_count: int
    areas: tuple[tuple[str, int], ...]
    read_errors: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_findings": self.total_findings,
            "info_count": self.info_count,
            "warning_count": self.warning_count,
            "error_count": self.error_count,
            "critical_count": self.critical_count,
            "areas": {key: value for key, value in self.areas},
            "read_errors": self.read_errors,
        }


@dataclass(frozen=True)
class InvestigationFilter:
    area: str | None = None
    target_id: str | None = None
    alert_id: str | None = None
    failures_only: bool = False
    min_severity: InvestigationSeverity | None = None


@dataclass(frozen=True)
class DashboardInvestigationSnapshot:
    generated_at: datetime
    health: DashboardHealthStatus
    summary: InvestigationSummary
    findings: tuple[InvestigationFinding, ...]
    dashboard_summary: DashboardSummary
    crawler: CrawlerDashboardSummary
    price: PriceDashboardSummary
    alerts: AlertDashboardSummary
    notifications: NotificationDashboardSummary
    runner: RunnerDashboardSummary
    audit: AuditDashboardSummary

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": _iso(self.generated_at),
            "health": self.health.value,
            "summary": self.summary.to_dict(),
            "findings": [item.to_dict() for item in self.findings],
            "dashboard_summary": self.dashboard_summary.to_dict(),
            "crawler": self.crawler.to_dict(),
            "price": self.price.to_dict(),
            "alerts": self.alerts.to_dict(),
            "notifications": self.notifications.to_dict(),
            "runner": self.runner.to_dict(),
            "audit": self.audit.to_dict(),
        }


def summarize_findings(findings: list[InvestigationFinding]) -> InvestigationSummary:
    info_count = sum(1 for item in findings if item.severity is InvestigationSeverity.INFO)
    warning_count = sum(1 for item in findings if item.severity is InvestigationSeverity.WARNING)
    error_count = sum(1 for item in findings if item.severity is InvestigationSeverity.ERROR)
    critical_count = sum(1 for item in findings if item.severity is InvestigationSeverity.CRITICAL)
    area_counts: dict[str, int] = {}
    read_errors = 0
    for item in findings:
        area_counts[item.area] = area_counts.get(item.area, 0) + 1
        if item.code.endswith("_READ_ERROR"):
            read_errors += 1
    areas = tuple(sorted(area_counts.items(), key=lambda pair: (-pair[1], pair[0])))
    return InvestigationSummary(
        total_findings=len(findings),
        info_count=info_count,
        warning_count=warning_count,
        error_count=error_count,
        critical_count=critical_count,
        areas=areas,
        read_errors=read_errors,
    )


def sort_findings(findings: list[InvestigationFinding]) -> list[InvestigationFinding]:
    return sorted(
        findings,
        key=lambda item: (
            -SEVERITY_ORDER[item.severity],
            -(item.occurred_at.timestamp() if item.occurred_at else 0),
            item.finding_id,
        ),
    )


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=utc_now().tzinfo)
    return value.isoformat()
