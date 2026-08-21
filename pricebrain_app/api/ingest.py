"""Ingest API — docs/09 §8 (FastAPI → Pipeline → Repository)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Security
from google.cloud.firestore_v1 import Client as FirestoreClient

from pricebrain_app.api.deps import get_firestore, require_ingest_api_key
from pricebrain_app.pipeline.exceptions import (
    GpuProductFilteredError,
    PipelineValidationError,
)
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository.exceptions import RepositoryValidationError
from pricebrain_app.repository.operational_service import persist_pipeline_validation_failure
from pricebrain_app.repository.service import save_validated_product

router = APIRouter(prefix="/internal", tags=["ingest"])


@router.post("/ingest/listing")
def ingest_listing(
    payload: dict[str, Any],
    _: None = Security(require_ingest_api_key),
    db: FirestoreClient = Depends(get_firestore),
) -> dict[str, str | bool]:
    try:
        validated = run_pipeline(payload)
        result = save_validated_product(db, dict(validated))
    except (PipelineValidationError, GpuProductFilteredError) as exc:
        persist_pipeline_validation_failure(
            db, exc, source="pipeline", raw_data=payload
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RepositoryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "ok", **result}
