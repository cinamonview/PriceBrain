"""Read-only operations command center DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pricebrain_app.crawler.dashboard_operations_models import DashboardFilter
from pricebrain_app.crawler.execution_operations_models import ExecutionOperationsSnapshot
from pricebrain_app.crawler.investigation_operations_models import DashboardInvestigationSnapshot
from pricebrain_app.crawler.remediation_operations_models import RemediationPlan
from pricebrain_app.crawler.targets import utc_now


@dataclass(frozen=True)
class CommandCenterFilter:
    mall_id: str | None = None
    category: str | None = "gpu"
    tag: str | None = None
    recent: int = 10
    failures_only: bool = False
    blocked_only: bool = False
    action_id: str | None = None
    target_id: str | None = None
    alert_id: str | None = None

    def dashboard_filter(self) -> DashboardFilter:
        return DashboardFilter(
            mall_id=self.mall_id,
            category=self.category,
            tag=self.tag,
            recent=max(int(self.recent), 1),
            failures_only=self.failures_only,
        )


@dataclass(frozen=True)
class CommandCenterSnapshot:
    generated_at: datetime
    dashboard: dict[str, Any]
    investigation: dict[str, Any]
    remediation: dict[str, Any]
    execution: dict[str, Any]
    health: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": _iso(self.generated_at),
            "dashboard": self.dashboard,
            "investigation": self.investigation,
            "remediation": self.remediation,
            "execution": self.execution,
            "health": self.health,
        }


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=utc_now().tzinfo)
    return value.isoformat()
