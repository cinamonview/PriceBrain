"""Read-only dashboard operations API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from pricebrain_app.api.operations.contract import build_command_center_response, build_operations_response, invoke_operations_route
from pricebrain_app.api.operations.dependencies import get_dashboard_operations_view
from pricebrain_app.api.operations.errors import OPERATIONS_ERROR_RESPONSES
from pricebrain_app.api.operations.models import READ_ONLY_DESCRIPTION, dashboard_filter
from pricebrain_app.api.operations.schemas import DashboardResponse
from pricebrain_app.crawler.dashboard_operations_view import DashboardOperationsView

router = APIRouter(tags=["operations-dashboard"])


@router.get(
    "/dashboard",
    summary="Operations dashboard",
    description=READ_ONLY_DESCRIPTION,
    response_model=DashboardResponse,
    responses=OPERATIONS_ERROR_RESPONSES,
)
def get_operations_dashboard(
    category: str | None = Query(default="gpu"),
    mall: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    recent: int = Query(default=10, ge=1),
    failures: bool = Query(default=False),
    view: DashboardOperationsView = Depends(get_dashboard_operations_view),
) -> DashboardResponse:
    def _build() -> DashboardResponse:
        snapshot = view.build_dashboard_snapshot(
            filters=dashboard_filter(
                category=category,
                mall=mall,
                tag=tag,
                recent=recent,
                failures=failures,
            )
        )
        return build_operations_response(DashboardResponse, snapshot.to_dict())

    return invoke_operations_route(_build)
