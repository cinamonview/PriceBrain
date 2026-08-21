"""Operations API contract helpers."""

from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar

from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError

from pricebrain_app.api.operations.errors import INTERNAL_SERVER_ERROR
from pricebrain_app.api.operations.models import redact_payload
from pricebrain_app.api.operations.schemas import (
    AuditResponse,
    CommandCenterHealthSchema,
    CommandCenterResponse,
    DashboardResponse,
    ExecutionResponse,
    InvestigationResponse,
    RemediationPlanResponse,
)

logger = logging.getLogger("pricebrain_app.api.operations")

OPERATIONS_ENDPOINTS: tuple[str, ...] = (
    "/api/operations/dashboard",
    "/api/operations/investigation",
    "/api/operations/remediation",
    "/api/operations/execution",
    "/api/operations/audit",
    "/api/operations/command-center",
)

FORBIDDEN_OPERATIONS_METHODS: frozenset[str] = frozenset({"post", "put", "patch", "delete"})

T = TypeVar("T", bound=BaseModel)


def invoke_operations_route(builder: Callable[[], T]) -> T:
    try:
        return builder()
    except HTTPException:
        raise
    except Exception:
        logger.exception("operations.api.route_error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=INTERNAL_SERVER_ERROR,
        )


def build_operations_response(model: type[T], payload: dict[str, Any]) -> T:
    redacted = redact_payload(payload)
    try:
        return model.model_validate(redacted)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=INTERNAL_SERVER_ERROR,
        ) from exc


def build_command_center_response(payload: dict[str, Any]) -> CommandCenterResponse:
    redacted = redact_payload(payload)
    try:
        return CommandCenterResponse(
            generated_at=redacted["generated_at"],
            dashboard=DashboardResponse.model_validate(redacted["dashboard"]),
            investigation=InvestigationResponse.model_validate(redacted["investigation"]),
            remediation=RemediationPlanResponse.model_validate(redacted["remediation"]),
            execution=ExecutionResponse.model_validate(redacted["execution"]),
            health=CommandCenterHealthSchema.model_validate(redacted["health"]),
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=INTERNAL_SERVER_ERROR,
        ) from exc
