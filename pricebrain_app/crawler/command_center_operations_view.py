"""Read-only operations command center aggregation."""

from __future__ import annotations

from datetime import datetime

from pricebrain_app.crawler.command_center_operations_models import CommandCenterFilter, CommandCenterSnapshot
from pricebrain_app.crawler.dashboard_operations_view import DashboardOperationsView
from pricebrain_app.crawler.execution_operations_models import ExecutionHistoryFilter
from pricebrain_app.crawler.execution_operations_view import ExecutionOperationsView
from pricebrain_app.crawler.investigation_operations_view import InvestigationOperationsView
from pricebrain_app.crawler.logging_utils import get_crawler_logger
from pricebrain_app.crawler.remediation_operations_view import RemediationOperationsView
from pricebrain_app.crawler.targets import utc_now

logger = get_crawler_logger("crawler.command_center_operations")


class CommandCenterOperationsView:
    """Compose dashboard, investigation, remediation, and execution views."""

    def __init__(
        self,
        dashboard_view: DashboardOperationsView,
        investigation_view: InvestigationOperationsView,
        remediation_view: RemediationOperationsView,
        execution_view: ExecutionOperationsView,
    ) -> None:
        self._dashboard = dashboard_view
        self._investigation = investigation_view
        self._remediation = remediation_view
        self._execution = execution_view

    def build_snapshot(
        self,
        *,
        filters: CommandCenterFilter | None = None,
        now: datetime | None = None,
    ) -> CommandCenterSnapshot:
        run_at = now or utc_now()
        flt = filters or CommandCenterFilter()
        dashboard_filters = flt.dashboard_filter()
        dashboard = self._dashboard.build_dashboard_snapshot(filters=dashboard_filters, now=run_at)
        investigation = self._investigation.investigate_dashboard(
            dashboard_filters=dashboard_filters,
            now=run_at,
        )
        remediation = self._remediation.build_remediation_plan(
            dashboard_filters=dashboard_filters,
            now=run_at,
        )
        execution_filters = ExecutionHistoryFilter(
            action_id=flt.action_id,
            target_id=flt.target_id,
            alert_id=flt.alert_id,
            failures_only=flt.failures_only,
            blocked_only=flt.blocked_only,
            recent=flt.recent,
        )
        execution = self._execution.build_snapshot(filters=execution_filters, now=run_at)
        health = {
            "dashboard": dashboard.summary.health.value,
            "dashboard_reasons": list(dashboard.summary.reasons),
            "execution": execution.health.value,
            "execution_reasons": list(execution.health_reasons),
        }
        logger.info(
            "command_center.operations.viewed",
            extra={
                "event": "command_center.operations.viewed",
                "dashboard_health": dashboard.summary.health.value,
                "execution_health": execution.health.value,
            },
        )
        return CommandCenterSnapshot(
            generated_at=run_at,
            dashboard=dashboard.to_dict(),
            investigation=investigation.to_dict(),
            remediation=_remediation_dict(remediation),
            execution=execution.to_dict(),
            health=health,
        )


def _remediation_dict(plan) -> dict:
    return plan.to_dict()
