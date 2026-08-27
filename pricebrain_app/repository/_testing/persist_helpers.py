"""Test-only persist helper. Application code must use persist_service."""

from __future__ import annotations

from typing import Any

from google.cloud.firestore_v1 import Client as FirestoreClient

from pricebrain_app.repository.service import _write_validated_product


def save_validated_product(
    db: FirestoreClient,
    data: dict[str, Any],
) -> dict[str, str | bool]:
    """Direct identity-checked persist for tests. Not an application API."""
    return _write_validated_product(db, data)
