"""FastAPI dependencies."""

from __future__ import annotations

import secrets
from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.cloud.firestore_v1 import Client as FirestoreClient

from pricebrain_app.config.settings import get_settings
from pricebrain_app.firebase.admin import get_firestore_client

# OpenAPI / Swagger Authorize — sends Authorization: Bearer <token>
bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="IngestAPIKey",
    description="PRICEBRAIN_INGEST_API_KEY from .env (Bearer token)",
)


def get_firestore() -> Generator[FirestoreClient, None, None]:
    settings = get_settings()
    if not settings.firebase_configured:
        raise RuntimeError(
            "Firebase is not configured. Set FIREBASE_PROJECT_ID and "
            "GOOGLE_APPLICATION_CREDENTIALS or FIRESTORE_EMULATOR_HOST."
        )
    yield get_firestore_client()


def require_ingest_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> None:
    """Server-to-server ingest auth via Bearer token.

    Production: inject PRICEBRAIN_INGEST_API_KEY from Secret Manager
    into Cloud Run env (no key in image or source).
    """
    settings = get_settings()
    configured_key = settings.pricebrain_ingest_api_key.strip()
    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingest API is not configured",
        )

    auth_header = request.headers.get("Authorization")
    if credentials is None:
        if auth_header is not None and auth_header.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header",
                headers={"WWW-Authenticate": "Bearer"},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials.strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not secrets.compare_digest(token, configured_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
