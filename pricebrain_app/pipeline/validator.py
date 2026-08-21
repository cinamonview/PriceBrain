"""Data validation — docs/08 §22–§23, §24."""

from __future__ import annotations

from typing import Any

from pricebrain_app.pipeline.constants import MAX_PRICE_KRW
from pricebrain_app.pipeline.exceptions import GpuProductFilteredError, PipelineValidationError
from pricebrain_app.pipeline.gpu_parser import has_gpu_keyword
from pricebrain_app.pipeline.types import ValidatedProduct


def _require_field(data: dict[str, Any], field: str) -> Any:
    value = data.get(field)
    if value is None or value == "":
        raise PipelineValidationError(
            f"{field} is required",
            field=field,
        )
    return value


def validate(data: dict[str, Any]) -> ValidatedProduct:
    product_id = _require_field(data, "product_id")

    raw_name = data.get("raw_product_name") or data.get("product_name")
    if not raw_name:
        raise PipelineValidationError("product_name is required", field="product_name")

    normalized_name = data.get("normalized_product_name")
    if not normalized_name:
        raise PipelineValidationError(
            "normalized_product_name is required",
            field="normalized_product_name",
        )

    mall_id = data.get("mall_id") or data.get("mall")
    if not mall_id:
        raise PipelineValidationError("mall is required", field="mall")

    product_url = data.get("product_url")
    if not product_url:
        raise PipelineValidationError("product_url is required", field="product_url")

    price = data.get("price")
    if price is None:
        raise PipelineValidationError("price is required", field="price")
    if not isinstance(price, int) or price <= 0:
        raise PipelineValidationError("price must be > 0", field="price")
    if price > MAX_PRICE_KRW:
        raise PipelineValidationError(
            f"price exceeds maximum ({MAX_PRICE_KRW})",
            field="price",
        )

    gpu_text = f"{raw_name} {normalized_name}"
    gpu_model = data.get("gpu_model")
    if not gpu_model and not has_gpu_keyword(gpu_text):
        raise GpuProductFilteredError("GPU keyword not detected")

    if not data.get("brand") or not data.get("gpu_model_id") or data.get("vram_gb") is None:
        raise PipelineValidationError(
            "structured GPU information is incomplete",
            field="gpu",
        )

    canonical_id = data.get("canonical_product_id")
    if not canonical_id:
        raise PipelineValidationError(
            "canonical_product_id generation failed",
            field="canonical_product_id",
        )

    validated: ValidatedProduct = {
        "mall": str(data.get("mall") or mall_id),
        "mall_id": str(mall_id),
        "product_id": str(product_id),
        "raw_product_name": str(raw_name),
        "normalized_product_name": str(normalized_name),
        "brand": str(data["brand"]),
        "board_partner_id": str(data.get("board_partner_id") or data["brand"]),
        "gpu_series": str(data.get("gpu_series", "")),
        "gpu_model": str(data.get("gpu_model", "")),
        "gpu_model_id": str(data["gpu_model_id"]),
        "vram_gb": int(data["vram_gb"]),
        "manufacturer_part_number": data.get("manufacturer_part_number"),
        "canonical_product_id": str(canonical_id),
        "price": int(price),
        "seller": str(data.get("seller", "")),
        "product_url": str(product_url),
        "availability": bool(data.get("availability", True)),
        "status": str(data.get("status", "AVAILABLE")),
    }

    if data.get("seller_id"):
        validated["seller_id"] = str(data["seller_id"])
    if data.get("image_url"):
        validated["image_url"] = str(data["image_url"])
    if data.get("crawled_at") is not None:
        validated["crawled_at"] = data["crawled_at"]

    return validated
