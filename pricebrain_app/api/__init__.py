"""FastAPI routes — SSOT: docs/09 §8, docs/13."""

from pricebrain_app.api.health import router as health_router
from pricebrain_app.api.ingest import router as ingest_router

__all__ = ["health_router", "ingest_router"]
