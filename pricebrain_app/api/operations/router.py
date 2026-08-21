"""Read-only operations API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from pricebrain_app.api.auth.dependencies import require_ops_viewer
from pricebrain_app.api.operations.routes_audit import router as audit_router
from pricebrain_app.api.operations.routes_command_center import router as command_center_router
from pricebrain_app.api.operations.routes_dashboard import router as dashboard_router
from pricebrain_app.api.operations.routes_execution import router as execution_router
from pricebrain_app.api.operations.routes_investigation import router as investigation_router
from pricebrain_app.api.operations.routes_remediation import router as remediation_router

router = APIRouter(
    prefix="/api/operations",
    dependencies=[Depends(require_ops_viewer)],
)
router.include_router(dashboard_router)
router.include_router(investigation_router)
router.include_router(remediation_router)
router.include_router(execution_router)
router.include_router(audit_router)
router.include_router(command_center_router)
