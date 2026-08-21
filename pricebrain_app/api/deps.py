"""FastAPI dependencies."""

from __future__ import annotations

import secrets
from collections.abc import Generator
from typing import Annotated

from fastapi import Header, HTTPException, status
from google.cloud.firestore_v1 import Client as FirestoreClient

from pricebrain_app.config.settings import get_settings
from pricebrain_app.firebase.admin import get_firestore_client


def get_firestore() -> Generator[FirestoreClient, None, None]:
    settings = get_settings()
    if not settings.firebase_configured:
        raise RuntimeError(
            "Firebase is not configured. Set FIREBASE_PROJECT_ID and "
            "GOOGLE_APPLICATION_CREDENTIALS or FIRESTORE_EMULATOR_HOST."
        )
    yield get_firestore_client()


def require_ingest_api_key(
    authorization: Annotated[str | None, Header()] = None,
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

    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header",
        )

    if not secrets.compare_digest(token.strip(), configured_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
