"""Read-only remediation plan operations API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from pricebrain_app.api.operations.contract import build_operations_response, invoke_operations_route
from pricebrain_app.api.operations.dependencies import get_remediation_operations_view
from pricebrain_app.api.operations.errors import OPERATIONS_ERROR_RESPONSES
from pricebrain_app.api.operations.models import READ_ONLY_DESCRIPTION, dashboard_filter
from pricebrain_app.api.operations.schemas import RemediationPlanResponse
from pricebrain_app.crawler.remediation_operations_models import RemediationFilter
from pricebrain_app.crawler.remediation_operations_view import RemediationOperationsView

router = APIRouter(tags=["operations-remediation"])


@router.get(
    "/remediation",
    summary="Operations remediation plan",
    description=READ_ONLY_DESCRIPTION,
    response_model=RemediationPlanResponse,
    responses=OPERATIONS_ERROR_RESPONSES,
)
def get_operations_remediation(
    priority: str | None = Query(default=None),
    area: str | None = Query(default=None),
    target_id: str | None = Query(default=None),
    alert_id: str | None = Query(default=None),
    failures: bool = Query(default=False),
    recent: int = Query(default=10, ge=1),
    category: str | None = Query(default="gpu"),
    mall: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    view: RemediationOperationsView = Depends(get_remediation_operations_view),
) -> RemediationPlanResponse:
    def _build() -> RemediationPlanResponse:
        dashboard_filters = dashboard_filter(
            category=category,
            mall=mall,
            tag=tag,
            recent=recent,
            failures=failures,
        )
        remediation_filters = RemediationFilter(
            area=area.lower() if area else None,
            target_id=target_id,
            alert_id=alert_id,
            priority=priority,
            failures_only=failures,
        )
        plan = view.build_remediation_plan(dashboard_filters=dashboard_filters)
        actions = view.actions(filters=remediation_filters, plan=plan)
        payload = plan.to_dict()
        payload["actions"] = [item.to_dict() for item in actions]
        return build_operations_response(RemediationPlanResponse, payload)

    return invoke_operations_route(_build)
