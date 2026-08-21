"""Read-only investigation operations API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from pricebrain_app.api.operations.contract import build_operations_response, invoke_operations_route
from pricebrain_app.api.operations.dependencies import get_investigation_operations_view
from pricebrain_app.api.operations.errors import OPERATIONS_ERROR_RESPONSES
from pricebrain_app.api.operations.models import READ_ONLY_DESCRIPTION, dashboard_filter
from pricebrain_app.api.operations.schemas import InvestigationResponse
from pricebrain_app.crawler.investigation_operations_models import InvestigationFilter
from pricebrain_app.crawler.investigation_operations_view import InvestigationOperationsView

router = APIRouter(tags=["operations-investigation"])


@router.get(
    "/investigation",
    summary="Operations investigation",
    description=READ_ONLY_DESCRIPTION,
    response_model=InvestigationResponse,
    responses=OPERATIONS_ERROR_RESPONSES,
)
def get_operations_investigation(
    area: str | None = Query(default=None),
    target_id: str | None = Query(default=None),
    alert_id: str | None = Query(default=None),
    failures: bool = Query(default=False),
    recent: int = Query(default=10, ge=1),
    category: str | None = Query(default="gpu"),
    mall: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    view: InvestigationOperationsView = Depends(get_investigation_operations_view),
) -> InvestigationResponse:
    def _build() -> InvestigationResponse:
        dashboard_filters = dashboard_filter(
            category=category,
            mall=mall,
            tag=tag,
            recent=recent,
            failures=failures,
        )
        investigation_filters = InvestigationFilter(
            area=area.lower() if area else None,
            target_id=target_id,
            alert_id=alert_id,
            failures_only=failures,
        )
        snapshot = view.investigate_dashboard(dashboard_filters=dashboard_filters)
        findings = view.findings(filters=investigation_filters, snapshot=snapshot)
        summary = view.summary(filters=investigation_filters, snapshot=snapshot)
        payload = snapshot.to_dict()
        payload["findings"] = [item.to_dict() for item in findings]
        payload["summary"] = summary.to_dict()
        return build_operations_response(InvestigationResponse, payload)

    return invoke_operations_route(_build)
