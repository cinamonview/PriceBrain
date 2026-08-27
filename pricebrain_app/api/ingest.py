"""Ingest API — docs/09 §8 (FastAPI → Pipeline → Repository)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, Security
from google.cloud.firestore_v1 import Client as FirestoreClient

from pricebrain_app.api.deps import get_firestore, require_ingest_api_key
from pricebrain_app.pipeline.exceptions import (
    GpuProductFilteredError,
    PipelineValidationError,
)
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository.exceptions import (
    RepositoryValidationError,
    UnknownGpuModelError,
)
from pricebrain_app.repository.operational_service import (
    persist_pipeline_validation_failure,
    quarantine_unknown_gpu_model,
)
from pricebrain_app.repository.persist_service import (
    IdentityReviewBlockedError,
    persist_validated_product,
)

router = APIRouter(prefix="/internal", tags=["ingest"])


@router.post("/ingest/listing")
def ingest_listing(
    payload: dict[str, Any],
    response: Response,
    _: None = Security(require_ingest_api_key),
    db: FirestoreClient = Depends(get_firestore),
) -> dict[str, str | bool]:
    validated_data: dict[str, Any] = {}
    try:
        validated = run_pipeline(payload)
        validated_data = dict(validated)
        external_id = str(
            validated_data.get("external_product_id")
            or validated_data.get("product_id")
            or payload.get("product_id")
            or ""
        )
        product_name = str(
            validated_data.get("normalized_product_name")
            or validated_data.get("raw_product_name")
            or payload.get("product_name")
            or ""
        )
        result = persist_validated_product(
            db,
            validated_data,
            external_product_id=external_id,
            product_name=product_name,
        )
    except IdentityReviewBlockedError as exc:
        response.status_code = 409
        return {
            "status": "identity_review_blocked",
            "canonical_product_id": exc.canonical_product_id,
            "review_reason": exc.review_reason,
            "detail": str(exc),
        }
    except (PipelineValidationError, GpuProductFilteredError) as exc:
        persist_pipeline_validation_failure(
            db, exc, source="pipeline", raw_data=payload
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except UnknownGpuModelError as exc:
        quarantine_unknown_gpu_model(db, exc, validated_data=validated_data)
        response.status_code = 202
        return {
            "status": "quarantined",
            "gpu_model_id": exc.gpu_model_id,
            "detail": str(exc),
        }
    except RepositoryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "ok", **result}
