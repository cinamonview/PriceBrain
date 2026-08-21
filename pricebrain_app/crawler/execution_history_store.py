"""In-memory remediation execution history store."""

from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Any

from pricebrain_app.crawler.execution_operations_models import (
    FORBIDDEN_METADATA_KEYS,
    ExecutionHistoryEntry,
    ExecutionHistoryStatus,
)
from pricebrain_app.crawler.logging_utils import get_crawler_logger
from pricebrain_app.crawler.remediation_executor_models import (
    RemediationExecutionMode,
    RemediationExecutionResult,
    RemediationExecutionStatus,
)
from pricebrain_app.crawler.remediation_operations_models import RemediationAction, RemediationPriority, RemediationRisk
from pricebrain_app.crawler.targets import parse_datetime, utc_now

logger = get_crawler_logger("crawler.execution_history")

_MAX_ENTRIES = 500

APPROVAL_FAILURE_CODES = frozenset(
    {
        "MISSING_APPROVAL_TOKEN",
        "INVALID_APPROVAL_TOKEN",
        "ACTION_ID_MISMATCH",
    }
)


class ExecutionHistoryStore:
    """Process-local bounded execution history."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._entries: deque[dict[str, Any]] = deque(maxlen=_MAX_ENTRIES)
        self._record_errors = 0

    @property
    def record_errors(self) -> int:
        with self._lock:
            return self._record_errors

    def record_execution(
        self,
        result: RemediationExecutionResult,
        *,
        action: RemediationAction | None = None,
    ) -> bool:
        try:
            entry = execution_entry_from_result(result, action=action)
            with self._lock:
                self._entries.appendleft(entry.to_dict())
            return True
        except Exception as exc:
            with self._lock:
                self._record_errors += 1
            logger.warning(
                "execution.history.record_failed",
                extra={"event": "execution.history.record_failed", "error": str(exc)},
            )
            return False

    def record_raw(self, payload: dict[str, Any]) -> bool:
        try:
            entry = parse_execution_history_entry(payload)
            with self._lock:
                self._entries.appendleft(entry.to_dict())
            return True
        except Exception as exc:
            with self._lock:
                self._record_errors += 1
            logger.warning(
                "execution.history.record_failed",
                extra={"event": "execution.history.record_failed", "error": str(exc)},
            )
            return False

    def list_raw(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._entries)
        if limit is not None:
            return items[: max(int(limit), 0)]
        return items

    def list_recent(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        return self.list_raw(limit=limit)

    def find_by_action(self, action_id: str) -> list[dict[str, Any]]:
        needle = action_id.strip()
        with self._lock:
            items = [item for item in self._entries if item.get("action_id") == needle]
        return items

    def find_by_target(self, target_id: str) -> list[dict[str, Any]]:
        needle = target_id.strip()
        with self._lock:
            items = [item for item in self._entries if item.get("target_id") == needle]
        return items

    def find_by_alert(self, alert_id: str) -> list[dict[str, Any]]:
        needle = alert_id.strip()
        with self._lock:
            items = [item for item in self._entries if item.get("alert_id") == needle]
        return items

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._record_errors = 0


_STORE = ExecutionHistoryStore()


def get_execution_history_store() -> ExecutionHistoryStore:
    return _STORE


def reset_execution_history_store() -> None:
    _STORE.clear()


def record_execution_history(
    result: RemediationExecutionResult,
    *,
    action: RemediationAction | None = None,
) -> bool:
    return get_execution_history_store().record_execution(result, action=action)


def execution_entry_from_result(
    result: RemediationExecutionResult,
    *,
    action: RemediationAction | None = None,
) -> ExecutionHistoryEntry:
    started_at = result.started_at
    completed_at = result.completed_at
    duration_ms = None
    if started_at and completed_at:
        duration_ms = max(int((completed_at - started_at).total_seconds() * 1000), 0)
    occurred_at = completed_at or started_at or utc_now()
    metadata = _sanitize_metadata(result.metadata)
    return ExecutionHistoryEntry(
        execution_id=result.execution_id,
        action_id=result.action_id,
        action_type=result.action_type,
        mode=result.mode.value,
        status=_history_status(result),
        priority=action.priority if action else RemediationPriority.MEDIUM,
        risk=action.risk if action else RemediationRisk.MEDIUM,
        area=action.area if action else "unknown",
        target_id=result.target_id,
        alert_id=result.alert_id,
        title=action.title if action else "",
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=duration_ms,
        mutation_performed=result.mutation_performed,
        approval_verified=result.approval_verified,
        error_code=result.error_code,
        message=result.message,
        occurred_at=occurred_at,
        metadata=metadata,
    )


def parse_execution_history_entry(payload: dict[str, Any]) -> ExecutionHistoryEntry:
    from pricebrain_app.crawler.remediation_operations_models import RemediationActionType, RemediationPriority, RemediationRisk

    action_type = RemediationActionType(str(payload["action_type"]))
    status = ExecutionHistoryStatus(str(payload.get("status", ExecutionHistoryStatus.UNKNOWN.value)))
    priority = RemediationPriority(str(payload.get("priority", RemediationPriority.MEDIUM.value)))
    risk = RemediationRisk(str(payload.get("risk", RemediationRisk.MEDIUM.value)))
    return ExecutionHistoryEntry(
        execution_id=str(payload["execution_id"]),
        action_id=str(payload["action_id"]),
        action_type=action_type,
        mode=str(payload.get("mode", "PLAN")),
        status=status,
        priority=priority,
        risk=risk,
        area=str(payload.get("area", "unknown")),
        target_id=payload.get("target_id"),
        alert_id=payload.get("alert_id"),
        title=str(payload.get("title", "")),
        started_at=parse_datetime(payload.get("started_at")),
        completed_at=parse_datetime(payload.get("completed_at")),
        duration_ms=payload.get("duration_ms"),
        mutation_performed=bool(payload.get("mutation_performed", False)),
        approval_verified=bool(payload.get("approval_verified", False)),
        error_code=payload.get("error_code"),
        message=str(payload.get("message", "")),
        occurred_at=parse_datetime(payload.get("occurred_at")),
        metadata=_sanitize_metadata(payload.get("metadata") or {}),
    )


def _history_status(result: RemediationExecutionResult) -> ExecutionHistoryStatus:
    if result.status is RemediationExecutionStatus.SKIPPED:
        return ExecutionHistoryStatus.SKIPPED
    if result.status is RemediationExecutionStatus.BLOCKED:
        return ExecutionHistoryStatus.BLOCKED
    if result.status is RemediationExecutionStatus.FAILED:
        return ExecutionHistoryStatus.FAILED
    if result.mode is RemediationExecutionMode.PLAN:
        return ExecutionHistoryStatus.PLANNED
    if result.mode is RemediationExecutionMode.DRY_RUN:
        return ExecutionHistoryStatus.DRY_RUN
    if result.mode is RemediationExecutionMode.EXECUTE:
        if result.status is RemediationExecutionStatus.APPROVED:
            return ExecutionHistoryStatus.APPROVED
        if result.approval_verified and result.status is RemediationExecutionStatus.EXECUTED:
            return ExecutionHistoryStatus.EXECUTED
        if result.approval_verified:
            return ExecutionHistoryStatus.APPROVED
    return ExecutionHistoryStatus.UNKNOWN


def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        lowered = str(key).lower()
        if lowered in FORBIDDEN_METADATA_KEYS:
            continue
        if any(token in lowered for token in ("token", "authorization", "credential", "webhook", "api_key")):
            continue
        cleaned[key] = value
    return cleaned
