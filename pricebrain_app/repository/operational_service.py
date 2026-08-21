"""Operational persist helpers — validation_logs (docs/08 → docs/09)."""

from __future__ import annotations

from typing import Any

from google.cloud.firestore_v1 import Client as FirestoreClient

from pricebrain_app.pipeline.exceptions import (
    GpuProductFilteredError,
    PipelineValidationError,
)
from pricebrain_app.repository.validation_repository import ValidationRepository


def persist_pipeline_validation_failure(
    db: FirestoreClient,
    exc: PipelineValidationError | GpuProductFilteredError,
    *,
    source: str = "pipeline",
    raw_data: dict[str, Any] | None = None,
) -> str:
    """Persist pipeline validation failure via ValidationRepository (09 only)."""
    details: dict[str, Any] = {
        "message": str(exc),
        "validation_status": exc.status.value,
    }
    if exc.field:
        details["field"] = exc.field
    if raw_data:
        mall_id = raw_data.get("mall_id") or raw_data.get("mall")
        if mall_id:
            details["mall_id"] = str(mall_id)
        if raw_data.get("product_id"):
            details["product_id"] = str(raw_data["product_id"])
        product_name = raw_data.get("product_name") or raw_data.get("raw_product_name")
        if product_name:
            details["product_name"] = str(product_name)
    return ValidationRepository(db).log_validation_failure(source, details)
