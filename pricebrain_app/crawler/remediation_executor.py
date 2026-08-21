"""Remediation action executor — plan, dry-run, and approved execute."""

from __future__ import annotations

import uuid
from datetime import datetime

from pricebrain_app.crawler.remediation_action_handlers import (
    RemediationActionHandler,
    RemediationHandlerContext,
    build_remediation_handlers,
)
from pricebrain_app.crawler.remediation_approval import RemediationApprovalVerifier, get_remediation_approval_verifier
from pricebrain_app.crawler.remediation_audit_events import record_remediation_execution
from pricebrain_app.crawler.execution_history_store import record_execution_history
from pricebrain_app.crawler.remediation_executor_models import (
    RemediationExecutionMode,
    RemediationExecutionResult,
    RemediationExecutionStatus,
)
from pricebrain_app.crawler.remediation_operations_models import RemediationAction, RemediationActionType
from pricebrain_app.crawler.targets import utc_now


class RemediationActionExecutor:
    """Execute remediation actions under strict approval and mode boundaries."""

    def __init__(
        self,
        context: RemediationHandlerContext,
        *,
        handlers: dict[RemediationActionType, RemediationActionHandler] | None = None,
        approval_verifier: RemediationApprovalVerifier | None = None,
        record_audit: bool = True,
    ) -> None:
        self._context = context
        self._handlers = handlers or build_remediation_handlers()
        self._approval = approval_verifier or get_remediation_approval_verifier()
        self._record_audit = record_audit

    def execute(
        self,
        action: RemediationAction,
        mode: RemediationExecutionMode = RemediationExecutionMode.PLAN,
        *,
        approval_token: str | None = None,
        now: datetime | None = None,
    ) -> RemediationExecutionResult:
        started_at = now or utc_now()
        base = _base_result(action, mode=mode, started_at=started_at)

        validation_error = _validate_action(action)
        if validation_error is not None:
            result = _finalize(
                base,
                status=RemediationExecutionStatus.BLOCKED,
                message=validation_error,
                error_code="MALFORMED_ACTION",
                started_at=started_at,
            )
            self._maybe_record(result, action)
            return result

        if action.action_type is RemediationActionType.NO_ACTION:
            result = _finalize(
                base,
                status=RemediationExecutionStatus.SKIPPED,
                message="No action required",
                started_at=started_at,
            )
            self._maybe_record(result, action)
            return result

        handler = self._handlers.get(action.action_type)
        if handler is None:
            result = _finalize(
                base,
                status=RemediationExecutionStatus.BLOCKED,
                message=f"No handler for action type: {action.action_type.value}",
                error_code="MISSING_HANDLER",
                started_at=started_at,
            )
            self._maybe_record(result, action)
            return result

        if mode is RemediationExecutionMode.PLAN:
            result = _finalize(
                base,
                status=RemediationExecutionStatus.PLANNED,
                message=f"Planned review: {action.action_type.value}",
                started_at=started_at,
                metadata={"planned": True},
            )
            self._maybe_record(result, action)
            return result

        if mode is RemediationExecutionMode.DRY_RUN:
            try:
                handler_result = handler.handle(action, self._context)
            except Exception as exc:
                result = _finalize(
                    base,
                    status=RemediationExecutionStatus.FAILED,
                    message=str(exc),
                    error_code="HANDLER_EXCEPTION",
                    started_at=started_at,
                )
                self._maybe_record(result, action)
                return result
            result = _finalize(
                base,
                status=RemediationExecutionStatus.EXECUTED,
                message=f"Dry-run OK: {handler_result.message}",
                started_at=started_at,
                metadata={"dry_run": True, **handler_result.metadata},
            )
            self._maybe_record(result, action)
            return result

        approval = self._approval.verify(
            action_id=action.action_id,
            approval_token=approval_token,
            human_approval_required=action.human_approval_required,
            auto_executable=action.auto_executable,
        )
        if not approval.verified:
            result = _finalize(
                base,
                status=RemediationExecutionStatus.BLOCKED,
                message=approval.message,
                error_code=approval.error_code,
                started_at=started_at,
                approval_verified=False,
            )
            self._maybe_record(result, action)
            return result

        try:
            handler_result = handler.handle(action, self._context)
        except Exception as exc:
            result = _finalize(
                base,
                status=RemediationExecutionStatus.FAILED,
                message=str(exc),
                error_code="HANDLER_EXCEPTION",
                started_at=started_at,
                approval_verified=True,
            )
            self._maybe_record(result, action)
            return result

        result = _finalize(
            base,
            status=RemediationExecutionStatus.EXECUTED,
            message=handler_result.message,
            started_at=started_at,
            approval_verified=True,
            metadata=handler_result.metadata,
            mutation_performed=handler_result.mutation_performed,
        )
        self._maybe_record(result, action)
        return result

    def _maybe_record(self, result: RemediationExecutionResult, action: RemediationAction) -> None:
        record_execution_history(result, action=action)
        if self._record_audit:
            record_remediation_execution(result)


def _validate_action(action: RemediationAction) -> str | None:
    if action.read_error is not None:
        return f"Malformed action: {action.read_error}"
    if not action.action_id.strip():
        return "Missing action_id"
    if not action.finding_id.strip():
        return "Missing finding_id"
    if action.human_approval_required is False and action.auto_executable is False:
        return None
    return None


def _base_result(
    action: RemediationAction,
    *,
    mode: RemediationExecutionMode,
    started_at: datetime,
) -> RemediationExecutionResult:
    return RemediationExecutionResult(
        execution_id=uuid.uuid4().hex,
        action_id=action.action_id,
        action_type=action.action_type,
        mode=mode,
        status=RemediationExecutionStatus.PLANNED,
        target_id=action.target_id,
        alert_id=action.alert_id,
        started_at=started_at,
        approval_required=action.human_approval_required,
    )


def _finalize(
    base: RemediationExecutionResult,
    *,
    status: RemediationExecutionStatus,
    message: str,
    started_at: datetime,
    error_code: str | None = None,
    approval_verified: bool = False,
    metadata: dict | None = None,
    mutation_performed: bool = False,
) -> RemediationExecutionResult:
    merged = dict(base.metadata)
    if metadata:
        merged.update(metadata)
    return RemediationExecutionResult(
        execution_id=base.execution_id,
        action_id=base.action_id,
        action_type=base.action_type,
        mode=base.mode,
        status=status,
        target_id=base.target_id,
        alert_id=base.alert_id,
        started_at=started_at,
        completed_at=utc_now(),
        message=message,
        error_code=error_code,
        mutation_performed=mutation_performed,
        approval_required=base.approval_required,
        approval_verified=approval_verified,
        metadata=merged,
    )
