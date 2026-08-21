"""Operations API error contract and exception handling."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from pricebrain_app.api.operations.schemas import OperationsErrorResponse

logger = logging.getLogger("pricebrain_app.api.operations")

OPERATIONS_ERROR_RESPONSES: dict[int, dict] = {
    401: {
        "model": OperationsErrorResponse,
        "description": "Missing, invalid, malformed, or expired authentication token",
    },
    403: {
        "model": OperationsErrorResponse,
        "description": "Authenticated user lacks required operations role",
    },
    500: {
        "model": OperationsErrorResponse,
        "description": "Unexpected internal server error",
    },
}

INTERNAL_SERVER_ERROR = "Internal server error"


def register_operations_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def operations_unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers,
            )
        if request.url.path.startswith("/api/operations"):
            logger.exception("operations.api.unhandled_error path=%s", request.url.path)
            return JSONResponse(status_code=500, content={"detail": INTERNAL_SERVER_ERROR})
        logger.exception("api.unhandled_error path=%s", request.url.path)
        return JSONResponse(status_code=500, content={"detail": INTERNAL_SERVER_ERROR})
