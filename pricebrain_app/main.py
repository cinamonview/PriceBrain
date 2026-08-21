"""FastAPI application entrypoint — docs/09, docs/13."""

from fastapi import FastAPI

from pricebrain_app.api.health import router as health_router
from pricebrain_app.api.ingest import router as ingest_router

app = FastAPI(
    title="PriceBrain API",
    description="Backend API — catalog write via Admin SDK (docs/13)",
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(ingest_router)
