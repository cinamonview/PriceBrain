"""Read-only remediation plan operations."""

from __future__ import annotations

from datetime import datetime

from pricebrain_app.crawler.dashboard_operations_models import DashboardFilter
from pricebrain_app.crawler.investigation_operations_view import InvestigationOperationsView
from pricebrain_app.crawler.logging_utils import get_crawler_logger
from pricebrain_app.crawler.remediation_operations_models import (
    PRIORITY_ORDER,
    RemediationAction,
    RemediationActionType,
    RemediationFilter,
    RemediationPlan,
    RemediationPriority,
    parse_remediation_priority,
    sort_actions,
    summarize_actions,
)
from pricebrain_app.crawler.remediation_rules import build_remediation_actions
from pricebrain_app.crawler.targets import utc_now

logger = get_crawler_logger("crawler.remediation_operations")
FAILURE_ACTION_TYPES = frozenset(
    {
        RemediationActionType.REVIEW_CRAWLER_TARGET,
        RemediationActionType.REVIEW_SSG_ACCESS,
        RemediationActionType.REVIEW_PRICE_HISTORY,
        RemediationActionType.REVIEW_ALERT,
        RemediationActionType.REVIEW_NOTIFICATION,
        RemediationActionType.REVIEW_RUNNER,
        RemediationActionType.REVIEW_AUDIT,
        RemediationActionType.VERIFY_CONFIGURATION,
    }
)


class RemediationOperationsView:
    """Build human-review remediation plans from investigation snapshots."""

    def __init__(self, investigation_view: InvestigationOperationsView) -> None:
        self._investigation = investigation_view
        self._last_plan: RemediationPlan | None = None

    def build_remediation_plan(
        self,
        *,
        dashboard_filters: DashboardFilter | None = None,
        now: datetime | None = None,
    ) -> RemediationPlan:
        run_at = now or utc_now()
        investigation = self._investigation.investigate_dashboard(
            dashboard_filters=dashboard_filters,
            now=run_at,
        )
        actions, read_errors = build_remediation_actions(investigation)
        sorted_actions = sort_actions(actions)
        actionable_findings = sum(
            1 for item in investigation.findings if item.severity.value != "INFO"
        )
        summary = summarize_actions(sorted_actions)
        plan = RemediationPlan(
            generated_at=run_at,
            health=investigation.health,
            total_findings=investigation.summary.total_findings,
            actionable_findings=actionable_findings,
            actions=tuple(sorted_actions),
            read_errors=read_errors + summary.read_errors,
            summary=summary,
        )
        self._last_plan = plan
        logger.info(
            "remediation.operations.viewed",
            extra={
                "event": "remediation.operations.viewed",
                "health": plan.health.value,
                "actionable_actions": summary.actionable_actions,
            },
        )
        return plan

    def actions(
        self,
        *,
        filters: RemediationFilter | None = None,
        plan: RemediationPlan | None = None,
    ) -> list[RemediationAction]:
        return _filter_actions(list((plan or self._require_plan()).actions), filters)

    def failures(
        self,
        *,
        plan: RemediationPlan | None = None,
    ) -> list[RemediationAction]:
        return self.actions(
            filters=RemediationFilter(failures_only=True),
            plan=plan,
        )

    def by_priority(
        self,
        priority: str,
        *,
        plan: RemediationPlan | None = None,
    ) -> list[RemediationAction]:
        return self.actions(
            filters=RemediationFilter(priority=priority),
            plan=plan,
        )

    def by_area(
        self,
        area: str,
        *,
        plan: RemediationPlan | None = None,
    ) -> list[RemediationAction]:
        return self.actions(filters=RemediationFilter(area=area), plan=plan)

    def for_target(
        self,
        target_id: str,
        *,
        filters: RemediationFilter | None = None,
        plan: RemediationPlan | None = None,
    ) -> list[RemediationAction]:
        flt = filters or RemediationFilter()
        merged = RemediationFilter(
            area=flt.area,
            target_id=target_id.strip(),
            alert_id=flt.alert_id,
            priority=flt.priority,
            failures_only=flt.failures_only,
        )
        return self.actions(filters=merged, plan=plan)

    def for_alert(
        self,
        alert_id: str,
        *,
        filters: RemediationFilter | None = None,
        plan: RemediationPlan | None = None,
    ) -> list[RemediationAction]:
        flt = filters or RemediationFilter()
        merged = RemediationFilter(
            area=flt.area,
            target_id=flt.target_id,
            alert_id=alert_id.strip(),
            priority=flt.priority,
            failures_only=flt.failures_only,
        )
        return self.actions(filters=merged, plan=plan)

    def _require_plan(self) -> RemediationPlan:
        if self._last_plan is None:
            return self.build_remediation_plan()
        return self._last_plan


def _filter_actions(
    actions: list[RemediationAction],
    filters: RemediationFilter | None,
) -> list[RemediationAction]:
    flt = filters or RemediationFilter()
    priority = parse_remediation_priority(flt.priority)
    filtered: list[RemediationAction] = []
    for item in actions:
        if flt.area is not None and item.area != flt.area.strip().lower():
            continue
        if flt.target_id is not None and item.target_id != flt.target_id.strip():
            continue
        if flt.alert_id is not None and item.alert_id != flt.alert_id.strip():
            continue
        if priority is not None and item.priority is not priority:
            continue
        if flt.failures_only and item.action_type is RemediationActionType.NO_ACTION:
            continue
        filtered.append(item)
    return sort_actions(filtered)
