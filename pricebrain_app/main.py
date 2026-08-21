"""FastAPI application entrypoint — docs/09, docs/13."""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from pricebrain_app.api.health import router as health_router
from pricebrain_app.api.ingest import router as ingest_router
from pricebrain_app.api.operations.contract import FORBIDDEN_OPERATIONS_METHODS, OPERATIONS_ENDPOINTS
from pricebrain_app.api.operations.errors import OPERATIONS_ERROR_RESPONSES, register_operations_exception_handlers
from pricebrain_app.api.operations.router import router as operations_router
from pricebrain_app.api.operations.schemas import OperationsErrorResponse

app = FastAPI(
    title="PriceBrain API",
    description="Backend API — catalog write via Admin SDK (docs/13)",
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(operations_router)
register_operations_exception_handlers(app)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    components = schema.setdefault("components", {})
    components.setdefault("securitySchemes", {})["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Firebase Authentication ID token",
    }
    error_schema = OperationsErrorResponse.model_json_schema(ref_template="#/components/schemas/{model}")
    components.setdefault("schemas", {})["OperationsErrorResponse"] = error_schema
    error_ref = {"$ref": "#/components/schemas/OperationsErrorResponse"}
    for path in OPERATIONS_ENDPOINTS:
        path_item = schema.get("paths", {}).get(path, {})
        for method, operation in path_item.items():
            if method in FORBIDDEN_OPERATIONS_METHODS:
                continue
            if not isinstance(operation, dict):
                continue
            operation.setdefault("security", [{"BearerAuth": []}])
            responses = operation.setdefault("responses", {})
            for status_code, meta in OPERATIONS_ERROR_RESPONSES.items():
                responses[str(status_code)] = {
                    "description": meta["description"],
                    "content": {"application/json": {"schema": error_ref}},
                }
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi
