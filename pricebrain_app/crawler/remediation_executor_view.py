"""Remediation executor operations view."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from pricebrain_app.crawler.dashboard_operations_models import DashboardFilter
from pricebrain_app.crawler.remediation_executor import RemediationActionExecutor
from pricebrain_app.crawler.remediation_executor_models import (
    RemediationExecutionMode,
    RemediationExecutionResult,
    RemediationExecutionStatus,
    RemediationPlanExecutionResult,
)
from pricebrain_app.crawler.remediation_operations_models import RemediationAction, RemediationPlan, sort_actions
from pricebrain_app.crawler.remediation_operations_view import RemediationOperationsView
from pricebrain_app.crawler.targets import utc_now


class RemediationExecutorView:
    """Plan, preview, dry-run, and approved execution of remediation actions."""

    def __init__(
        self,
        remediation_view: RemediationOperationsView,
        executor: RemediationActionExecutor,
    ) -> None:
        self._remediation = remediation_view
        self._executor = executor

    def preview(
        self,
        action: RemediationAction,
        *,
        now: datetime | None = None,
    ) -> RemediationExecutionResult:
        return self._executor.execute(action, RemediationExecutionMode.PLAN, now=now)

    def dry_run(
        self,
        action: RemediationAction,
        *,
        now: datetime | None = None,
    ) -> RemediationExecutionResult:
        return self._executor.execute(action, RemediationExecutionMode.DRY_RUN, now=now)

    def execute(
        self,
        action: RemediationAction,
        *,
        approval_token: str | None,
        now: datetime | None = None,
    ) -> RemediationExecutionResult:
        return self._executor.execute(
            action,
            RemediationExecutionMode.EXECUTE,
            approval_token=approval_token,
            now=now,
        )

    def execute_plan(
        self,
        plan: RemediationPlan,
        *,
        mode: RemediationExecutionMode = RemediationExecutionMode.PLAN,
        approval_token_provider: Callable[[RemediationAction], str | None] | None = None,
        now: datetime | None = None,
    ) -> RemediationPlanExecutionResult:
        run_at = now or utc_now()
        results: list[RemediationExecutionResult] = []
        read_errors = 0
        for action in sort_actions(list(plan.actions)):
            if action.action_type.value == "NO_ACTION":
                continue
            try:
                if mode is RemediationExecutionMode.EXECUTE:
                    token = approval_token_provider(action) if approval_token_provider else None
                    results.append(
                        self._executor.execute(
                            action,
                            RemediationExecutionMode.EXECUTE,
                            approval_token=token,
                            now=run_at,
                        )
                    )
                else:
                    results.append(self._executor.execute(action, mode, now=run_at))
            except Exception as exc:
                read_errors += 1
                results.append(
                    RemediationExecutionResult(
                        execution_id=f"error-{action.action_id}",
                        action_id=action.action_id,
                        action_type=action.action_type,
                        mode=mode,
                        status=RemediationExecutionStatus.FAILED,
                        message=str(exc),
                        error_code="EXECUTION_EXCEPTION",
                        started_at=run_at,
                        completed_at=utc_now(),
                    )
                )
        return RemediationPlanExecutionResult(mode=mode, results=tuple(results), read_errors=read_errors)

    def build_plan(
        self,
        *,
        dashboard_filters: DashboardFilter | None = None,
        now: datetime | None = None,
    ) -> RemediationPlan:
        return self._remediation.build_remediation_plan(dashboard_filters=dashboard_filters, now=now)

    def get_action(self, plan: RemediationPlan, action_id: str) -> RemediationAction | None:
        for action in plan.actions:
            if action.action_id == action_id.strip():
                return action
        return None
