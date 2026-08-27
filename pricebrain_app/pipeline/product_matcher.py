"""Product matching / canonical ID — docs/08 §18–§21, docs/05 §2.1."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from pricebrain_app.pipeline.identity_variants import extract_variant_token
from pricebrain_app.pipeline.utils import gpu_model_to_slug, seller_slug


def _slug_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "", value.upper())
    return token


def _extract_variant_tokens(normalized_name: str, *, brand: str | None = None) -> str | None:
    """Extract compact variant token(s) for canonical ID — docs/08 §19 example."""
    return extract_variant_token(brand=brand, normalized_name=normalized_name)


def build_canonical_product_id(data: dict[str, Any]) -> str | None:
    """docs/05 §2.1 priority order."""
    mpn = data.get("manufacturer_part_number")
    if mpn:
        return _slug_token(str(mpn))

    model_number = data.get("model_name")
    if model_number:
        slug = _slug_token(str(model_number))
        if slug:
            return slug

    brand = data.get("brand")
    gpu_model = data.get("gpu_model")
    vram_gb = data.get("vram_gb")
    normalized_name = data.get("normalized_product_name")
    if brand and gpu_model and vram_gb is not None:
        model_compact = gpu_model.replace(" ", "").upper()
        parts = [str(brand).upper(), model_compact]
        variant = _extract_variant_tokens(str(normalized_name or ""), brand=str(brand))
        if variant:
            parts.append(variant)
        parts.append(f"{int(vram_gb)}GB")
        return "-".join(parts)

    if normalized_name:
        digest = hashlib.sha1(str(normalized_name).encode("utf-8")).hexdigest()[:16]
        return f"NAME-{digest.upper()}"

    return None


def match_product(data: dict[str, Any]) -> dict[str, Any]:
    result = dict(data)

    brand = result.get("brand")
    if brand and not result.get("board_partner_id"):
        result["board_partner_id"] = str(brand).upper()

    gpu_model = result.get("gpu_model")
    if gpu_model and not result.get("gpu_model_id"):
        result["gpu_model_id"] = gpu_model_to_slug(str(gpu_model))

    mall_id = result.get("mall_id") or result.get("mall")
    seller = result.get("seller") or result.get("normalized_seller_name")
    if mall_id and seller:
        result["seller_id"] = f"{mall_id}_{seller_slug(str(seller))}"

    canonical_id = build_canonical_product_id(result)
    if canonical_id:
        result["canonical_product_id"] = canonical_id

    result.setdefault("availability", True)
    result.setdefault("status", "AVAILABLE")
    return result
