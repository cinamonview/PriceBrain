"""Remediation action executor DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pricebrain_app.crawler.remediation_operations_models import RemediationActionType
from pricebrain_app.crawler.targets import utc_now


class RemediationExecutionMode(str, Enum):
    PLAN = "PLAN"
    DRY_RUN = "DRY_RUN"
    EXECUTE = "EXECUTE"


class RemediationExecutionStatus(str, Enum):
    PLANNED = "PLANNED"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class RemediationExecutionResult:
    execution_id: str
    action_id: str
    action_type: RemediationActionType
    mode: RemediationExecutionMode
    status: RemediationExecutionStatus
    target_id: str | None = None
    alert_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    message: str = ""
    error_code: str | None = None
    mutation_performed: bool = False
    approval_required: bool = True
    approval_verified: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "mode": self.mode.value,
            "status": self.status.value,
            "target_id": self.target_id,
            "alert_id": self.alert_id,
            "started_at": _iso(self.started_at),
            "completed_at": _iso(self.completed_at),
            "message": self.message,
            "error_code": self.error_code,
            "mutation_performed": self.mutation_performed,
            "approval_required": self.approval_required,
            "approval_verified": self.approval_verified,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RemediationPlanExecutionResult:
    mode: RemediationExecutionMode
    results: tuple[RemediationExecutionResult, ...]
    read_errors: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "read_errors": self.read_errors,
            "results": [item.to_dict() for item in self.results],
        }


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=utc_now().tzinfo)
    return value.isoformat()
