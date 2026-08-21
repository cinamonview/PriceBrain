"""Read-only execution history operations API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from pricebrain_app.api.operations.contract import build_operations_response, invoke_operations_route
from pricebrain_app.api.operations.dependencies import get_execution_operations_view
from pricebrain_app.api.operations.errors import OPERATIONS_ERROR_RESPONSES
from pricebrain_app.api.operations.models import READ_ONLY_DESCRIPTION
from pricebrain_app.api.operations.schemas import ExecutionResponse
from pricebrain_app.crawler.execution_operations_models import ExecutionHistoryFilter
from pricebrain_app.crawler.execution_operations_view import ExecutionOperationsView

router = APIRouter(tags=["operations-execution"])


@router.get(
    "/execution",
    summary="Operations execution history",
    description=READ_ONLY_DESCRIPTION,
    response_model=ExecutionResponse,
    responses=OPERATIONS_ERROR_RESPONSES,
)
def get_operations_execution(
    status: str | None = Query(default=None),
    target_id: str | None = Query(default=None),
    alert_id: str | None = Query(default=None),
    action_id: str | None = Query(default=None),
    failures: bool = Query(default=False),
    blocked: bool = Query(default=False),
    recent: int = Query(default=10, ge=1),
    view: ExecutionOperationsView = Depends(get_execution_operations_view),
) -> ExecutionResponse:
    def _build() -> ExecutionResponse:
        filters = ExecutionHistoryFilter(
            action_id=action_id,
            target_id=target_id,
            alert_id=alert_id,
            failures_only=failures,
            blocked_only=blocked,
            recent=recent,
        )
        if failures:
            entries = view.failures(recent=recent)
        elif blocked:
            entries = view.blocked(recent=recent)
        else:
            entries = view.list_recent(filters=filters)

        if status:
            normalized = status.strip().upper()
            entries = [
                item
                for item in entries
                if item.entry is not None and item.entry.status.value == normalized
            ]

        snapshot = view.build_snapshot(filters=filters)
        payload = snapshot.to_dict()
        payload["entries"] = [item.to_dict() for item in entries[: max(int(recent), 0)]]
        return build_operations_response(ExecutionResponse, payload)

    return invoke_operations_route(_build)
