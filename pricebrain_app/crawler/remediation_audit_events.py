"""Record remediation execution outcomes in audit event store."""

from __future__ import annotations

import uuid
from datetime import datetime

from pricebrain_app.crawler.audit_event_store import get_audit_event_store
from pricebrain_app.crawler.audit_operations_models import AuditEvent, AuditEventType
from pricebrain_app.crawler.remediation_executor_models import (
    RemediationExecutionMode,
    RemediationExecutionResult,
    RemediationExecutionStatus,
)
from pricebrain_app.crawler.targets import utc_now


def record_remediation_execution(result: RemediationExecutionResult) -> None:
    event_type = _event_type_for(result)
    occurred_at = result.completed_at or result.started_at or utc_now()
    metadata = {
        "execution_id": result.execution_id,
        "mode": result.mode.value,
        "status": result.status.value,
        "action_type": result.action_type.value,
        "mutation_performed": result.mutation_performed,
        "approval_verified": result.approval_verified,
        "error_code": result.error_code,
    }
    if result.error_code:
        metadata["error_code"] = result.error_code
    get_audit_event_store().append(
        AuditEvent(
            event_id=uuid.uuid4().hex,
            event_type=event_type,
            occurred_at=occurred_at,
            alert_id=result.alert_id,
            target_id=result.target_id,
            status=result.status.value,
            message=result.message,
            metadata=metadata,
        )
    )


def _event_type_for(result: RemediationExecutionResult) -> AuditEventType:
    if result.mode is RemediationExecutionMode.PLAN:
        return AuditEventType.REMEDIATION_PLANNED
    if result.mode is RemediationExecutionMode.DRY_RUN:
        return AuditEventType.REMEDIATION_DRY_RUN
    if result.status is RemediationExecutionStatus.BLOCKED and result.error_code in {
        "MISSING_APPROVAL_TOKEN",
        "INVALID_APPROVAL_TOKEN",
        "ACTION_ID_MISMATCH",
    }:
        return AuditEventType.REMEDIATION_APPROVAL_BLOCKED
    if result.status is RemediationExecutionStatus.EXECUTED:
        return AuditEventType.REMEDIATION_EXECUTED
    if result.status in {RemediationExecutionStatus.FAILED, RemediationExecutionStatus.BLOCKED}:
        return AuditEventType.REMEDIATION_FAILED
    if result.status is RemediationExecutionStatus.SKIPPED:
        return AuditEventType.REMEDIATION_PLANNED
    return AuditEventType.REMEDIATION_PLANNED
