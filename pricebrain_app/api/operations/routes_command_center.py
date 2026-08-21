"""Read-only command center operations API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from pricebrain_app.api.operations.contract import build_command_center_response, invoke_operations_route
from pricebrain_app.api.operations.dependencies import get_command_center_operations_view
from pricebrain_app.api.operations.errors import OPERATIONS_ERROR_RESPONSES
from pricebrain_app.api.operations.models import READ_ONLY_DESCRIPTION
from pricebrain_app.api.operations.schemas import CommandCenterResponse
from pricebrain_app.crawler.command_center_operations_models import CommandCenterFilter
from pricebrain_app.crawler.command_center_operations_view import CommandCenterOperationsView

router = APIRouter(tags=["operations-command-center"])


@router.get(
    "/command-center",
    summary="Operations command center",
    description=READ_ONLY_DESCRIPTION,
    response_model=CommandCenterResponse,
    responses=OPERATIONS_ERROR_RESPONSES,
)
def get_operations_command_center(
    category: str | None = Query(default="gpu"),
    mall: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    recent: int = Query(default=10, ge=1),
    failures: bool = Query(default=False),
    blocked: bool = Query(default=False),
    view: CommandCenterOperationsView = Depends(get_command_center_operations_view),
) -> CommandCenterResponse:
    def _build() -> CommandCenterResponse:
        snapshot = view.build_snapshot(
            filters=CommandCenterFilter(
                mall_id=mall,
                category=category,
                tag=tag,
                recent=max(int(recent), 1),
                failures_only=failures,
                blocked_only=blocked,
            )
        )
        return build_command_center_response(snapshot.to_dict())

    return invoke_operations_route(_build)
