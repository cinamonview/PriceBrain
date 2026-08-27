"""Operational persist helpers — validation_logs (docs/08 → docs/09)."""

from __future__ import annotations

from typing import Any

from google.cloud.firestore_v1 import Client as FirestoreClient

from pricebrain_app.pipeline.exceptions import (
    GpuProductFilteredError,
    PipelineValidationError,
)
from pricebrain_app.pipeline.utils import normalize_mall_id
from pricebrain_app.repository.exceptions import UnknownGpuModelError
from pricebrain_app.repository.pending_gpu_model_repository import (
    PendingGpuModelRepository,
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


def quarantine_unknown_gpu_model(
    db: FirestoreClient,
    exc: UnknownGpuModelError,
    *,
    validated_data: dict[str, Any] | None = None,
) -> str:
    """Persist an unknown gpu_model_id to pending_gpu_models instead of discarding it.

    Only the model identity and reviewer evidence are stored — no seller, price or
    credential data, since none of it is needed to approve a GPU model.
    """
    data = validated_data or {}
    return PendingGpuModelRepository(db).record_unknown_model(
        gpu_model_id=exc.gpu_model_id,
        display_name=data.get("gpu_model") or None,
        gpu_series=data.get("gpu_series") or None,
        mall_id=normalize_mall_id(data.get("mall_id")),
        product_name=data.get("normalized_product_name")
        or data.get("raw_product_name")
        or None,
        product_url=data.get("product_url") or None,
    )
