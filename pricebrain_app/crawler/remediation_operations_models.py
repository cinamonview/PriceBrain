"""Read-only remediation plan DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pricebrain_app.crawler.dashboard_operations_models import DashboardHealthStatus
from pricebrain_app.crawler.targets import utc_now


class RemediationActionType(str, Enum):
    REVIEW_CRAWLER_TARGET = "REVIEW_CRAWLER_TARGET"
    REVIEW_SSG_ACCESS = "REVIEW_SSG_ACCESS"
    REVIEW_PRICE_HISTORY = "REVIEW_PRICE_HISTORY"
    REVIEW_ALERT = "REVIEW_ALERT"
    REVIEW_NOTIFICATION = "REVIEW_NOTIFICATION"
    REVIEW_RUNNER = "REVIEW_RUNNER"
    REVIEW_AUDIT = "REVIEW_AUDIT"
    VERIFY_CONFIGURATION = "VERIFY_CONFIGURATION"
    NO_ACTION = "NO_ACTION"


class RemediationPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RemediationRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


PRIORITY_ORDER = {
    RemediationPriority.CRITICAL: 4,
    RemediationPriority.HIGH: 3,
    RemediationPriority.MEDIUM: 2,
    RemediationPriority.LOW: 1,
}

RISK_ORDER = {
    RemediationRisk.HIGH: 3,
    RemediationRisk.MEDIUM: 2,
    RemediationRisk.LOW: 1,
}


@dataclass(frozen=True)
class RemediationAction:
    action_id: str
    action_type: RemediationActionType
    priority: RemediationPriority
    risk: RemediationRisk
    finding_id: str
    area: str
    title: str
    reason: str
    recommended_steps: tuple[str, ...]
    preconditions: tuple[str, ...] = ()
    target_id: str | None = None
    alert_id: str | None = None
    human_approval_required: bool = True
    auto_executable: bool = False
    read_error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "priority": self.priority.value,
            "risk": self.risk.value,
            "finding_id": self.finding_id,
            "area": self.area,
            "target_id": self.target_id,
            "alert_id": self.alert_id,
            "title": self.title,
            "reason": self.reason,
            "recommended_steps": list(self.recommended_steps),
            "preconditions": list(self.preconditions),
            "human_approval_required": self.human_approval_required,
            "auto_executable": self.auto_executable,
            "read_error": self.read_error,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RemediationPlanSummary:
    total_actions: int
    actionable_actions: int
    no_action_count: int
    by_priority: tuple[tuple[str, int], ...]
    by_area: tuple[tuple[str, int], ...]
    read_errors: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_actions": self.total_actions,
            "actionable_actions": self.actionable_actions,
            "no_action_count": self.no_action_count,
            "by_priority": {key: value for key, value in self.by_priority},
            "by_area": {key: value for key, value in self.by_area},
            "read_errors": self.read_errors,
        }


@dataclass(frozen=True)
class RemediationPlan:
    generated_at: datetime
    health: DashboardHealthStatus
    total_findings: int
    actionable_findings: int
    actions: tuple[RemediationAction, ...]
    read_errors: int
    summary: RemediationPlanSummary

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": _iso(self.generated_at),
            "health": self.health.value,
            "total_findings": self.total_findings,
            "actionable_findings": self.actionable_findings,
            "actions": [item.to_dict() for item in self.actions],
            "read_errors": self.read_errors,
            "summary": self.summary.to_dict(),
        }


@dataclass(frozen=True)
class RemediationFilter:
    area: str | None = None
    target_id: str | None = None
    alert_id: str | None = None
    priority: str | None = None
    failures_only: bool = False


def sort_actions(actions: list[RemediationAction]) -> list[RemediationAction]:
    return sorted(
        actions,
        key=lambda item: (
            -PRIORITY_ORDER[item.priority],
            -RISK_ORDER[item.risk],
            -(item.metadata.get("occurred_at_ts", 0) or 0),
            item.action_id,
        ),
    )


def summarize_actions(actions: list[RemediationAction]) -> RemediationPlanSummary:
    actionable = [item for item in actions if item.action_type is not RemediationActionType.NO_ACTION]
    no_action = sum(1 for item in actions if item.action_type is RemediationActionType.NO_ACTION)
    read_errors = sum(1 for item in actions if item.read_error is not None)
    by_priority: dict[str, int] = {}
    by_area: dict[str, int] = {}
    for item in actionable:
        by_priority[item.priority.value] = by_priority.get(item.priority.value, 0) + 1
        by_area[item.area] = by_area.get(item.area, 0) + 1
    return RemediationPlanSummary(
        total_actions=len(actions),
        actionable_actions=len(actionable),
        no_action_count=no_action,
        by_priority=tuple(sorted(by_priority.items(), key=lambda pair: (-PRIORITY_ORDER[RemediationPriority(pair[0])], pair[0]))),
        by_area=tuple(sorted(by_area.items(), key=lambda pair: (-pair[1], pair[0]))),
        read_errors=read_errors,
    )


def parse_remediation_priority(value: str | None) -> RemediationPriority | None:
    if value is None:
        return None
    key = value.strip().upper()
    try:
        return RemediationPriority(key)
    except ValueError:
        return None


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=utc_now().tzinfo)
    return value.isoformat()
