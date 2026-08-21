"""Read-only remediation execution history DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pricebrain_app.crawler.remediation_operations_models import RemediationActionType, RemediationPriority, RemediationRisk
from pricebrain_app.crawler.targets import utc_now


class ExecutionHistoryStatus(str, Enum):
    PLANNED = "PLANNED"
    DRY_RUN = "DRY_RUN"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    UNKNOWN = "UNKNOWN"


class ExecutionHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


STATUS_PRIORITY_ORDER = {
    ExecutionHistoryStatus.FAILED: 6,
    ExecutionHistoryStatus.BLOCKED: 5,
    ExecutionHistoryStatus.EXECUTED: 4,
    ExecutionHistoryStatus.APPROVED: 3,
    ExecutionHistoryStatus.DRY_RUN: 2,
    ExecutionHistoryStatus.PLANNED: 1,
    ExecutionHistoryStatus.SKIPPED: 0,
    ExecutionHistoryStatus.UNKNOWN: 0,
}

FORBIDDEN_METADATA_KEYS = frozenset(
    {
        "approval_token",
        "api_key",
        "authorization",
        "credential",
        "webhook_url",
        "webhook",
    }
)


@dataclass(frozen=True)
class ExecutionHistoryEntry:
    execution_id: str
    action_id: str
    action_type: RemediationActionType
    mode: str
    status: ExecutionHistoryStatus
    priority: RemediationPriority = RemediationPriority.MEDIUM
    risk: RemediationRisk = RemediationRisk.MEDIUM
    area: str = "unknown"
    target_id: str | None = None
    alert_id: str | None = None
    title: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    mutation_performed: bool = False
    approval_verified: bool = False
    error_code: str | None = None
    message: str = ""
    occurred_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "mode": self.mode,
            "status": self.status.value,
            "priority": self.priority.value,
            "risk": self.risk.value,
            "area": self.area,
            "target_id": self.target_id,
            "alert_id": self.alert_id,
            "title": self.title,
            "started_at": _iso(self.started_at),
            "completed_at": _iso(self.completed_at),
            "duration_ms": self.duration_ms,
            "mutation_performed": self.mutation_performed,
            "approval_verified": self.approval_verified,
            "error_code": self.error_code,
            "message": self.message,
            "occurred_at": _iso(self.occurred_at),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ExecutionHistorySnapshot:
    entry: ExecutionHistoryEntry | None = None
    read_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry": self.entry.to_dict() if self.entry else None,
            "read_error": self.read_error,
        }


@dataclass(frozen=True)
class ExecutionHistoryFilter:
    action_id: str | None = None
    target_id: str | None = None
    alert_id: str | None = None
    failures_only: bool = False
    blocked_only: bool = False
    recent: int | None = None


@dataclass(frozen=True)
class ExecutionHistorySummary:
    total: int = 0
    planned: int = 0
    dry_run: int = 0
    approved: int = 0
    executed: int = 0
    blocked: int = 0
    failed: int = 0
    skipped: int = 0
    mutation_count: int = 0
    approval_failures: int = 0
    recent_failures: int = 0
    by_action_type: tuple[tuple[str, int], ...] = ()
    by_area: tuple[tuple[str, int], ...] = ()
    read_errors: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "planned": self.planned,
            "dry_run": self.dry_run,
            "approved": self.approved,
            "executed": self.executed,
            "blocked": self.blocked,
            "failed": self.failed,
            "skipped": self.skipped,
            "mutation_count": self.mutation_count,
            "approval_failures": self.approval_failures,
            "recent_failures": self.recent_failures,
            "by_action_type": {key: value for key, value in self.by_action_type},
            "by_area": {key: value for key, value in self.by_area},
            "read_errors": self.read_errors,
        }


@dataclass(frozen=True)
class ExecutionOperationsSnapshot:
    generated_at: datetime
    summary: ExecutionHistorySummary
    health: ExecutionHealthStatus
    health_reasons: tuple[str, ...]
    entries: tuple[ExecutionHistorySnapshot, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": _iso(self.generated_at),
            "summary": self.summary.to_dict(),
            "health": self.health.value,
            "health_reasons": list(self.health_reasons),
            "entries": [item.to_dict() for item in self.entries],
        }


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=utc_now().tzinfo)
    return value.isoformat()
