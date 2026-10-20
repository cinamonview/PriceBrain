"""Price analysis API — PRD §11, §13, §14 (read-only, catalog data)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from google.cloud.firestore_v1 import Client as FirestoreClient

from pricebrain_app.analysis.models import (
    DEFAULT_WINDOW_DAYS,
    SUPPORTED_WINDOW_DAYS,
    ProductPriceAnalysis,
)
from pricebrain_app.analysis.product_analysis import analyze_product
from pricebrain_app.api.deps import get_firestore
from pricebrain_app.repository.price_analysis_repository import PriceAnalysisRepository

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/products/{product_id}", response_model=ProductPriceAnalysis)
def get_product_price_analysis(
    product_id: str,
    window_days: int = Query(
        DEFAULT_WINDOW_DAYS,
        description=f"분석 기간(일). 허용값: {', '.join(map(str, SUPPORTED_WINDOW_DAYS))}",
    ),
    db: FirestoreClient = Depends(get_firestore),
    now: datetime = Depends(_utcnow),
) -> ProductPriceAnalysis:
    if window_days not in SUPPORTED_WINDOW_DAYS:
        raise HTTPException(
            status_code=422,
            detail=f"window_days must be one of {list(SUPPORTED_WINDOW_DAYS)}",
        )
    repository = PriceAnalysisRepository(db)
    listings = repository.list_listing_histories(product_id)
    product = repository.get_product(product_id)
    if not listings and product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return analyze_product(
        product_id=product_id,
        product_name=(product or {}).get("normalized_product_name"),
        listings=listings,
        window_days=window_days,
        now=now,
    )
