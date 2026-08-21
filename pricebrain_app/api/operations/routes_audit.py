"""Read-only audit event history operations API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from pricebrain_app.api.operations.contract import build_operations_response, invoke_operations_route
from pricebrain_app.api.operations.dependencies import get_audit_operations_view
from pricebrain_app.api.operations.errors import OPERATIONS_ERROR_RESPONSES
from pricebrain_app.api.operations.models import READ_ONLY_DESCRIPTION
from pricebrain_app.api.operations.schemas import AuditResponse
from pricebrain_app.crawler.audit_operations_models import AuditEventFilter
from pricebrain_app.crawler.audit_operations_view import AuditOperationsView

router = APIRouter(tags=["operations-audit"])


@router.get(
    "/audit",
    summary="Operations audit event history",
    description=READ_ONLY_DESCRIPTION,
    response_model=AuditResponse,
    responses=OPERATIONS_ERROR_RESPONSES,
)
def get_operations_audit(
    event_type: str | None = Query(default=None),
    alert_id: str | None = Query(default=None),
    target_id: str | None = Query(default=None),
    mall: str | None = Query(default=None),
    status: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    failures: bool = Query(default=False),
    recent: int = Query(default=50, ge=1),
    view: AuditOperationsView = Depends(get_audit_operations_view),
) -> AuditResponse:
    def _build() -> AuditResponse:
        filters = AuditEventFilter(
            event_type=event_type,
            alert_id=alert_id,
            target_id=target_id,
            mall_id=mall,
            status=status,
            channel=channel,
            failures_only=failures,
            recent=recent,
        )
        snapshot = view.build_snapshot(filters=filters)
        return build_operations_response(AuditResponse, snapshot.to_dict())

    return invoke_operations_route(_build)
