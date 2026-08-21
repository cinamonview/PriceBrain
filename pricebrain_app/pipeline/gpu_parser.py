"""GPU information extraction — docs/08 §12–§17, §24."""

from __future__ import annotations

import re
from typing import Any

from pricebrain_app.pipeline.constants import GPU_BOARD_PARTNERS, GPU_FILTER_KEYWORDS
from pricebrain_app.pipeline.utils import gpu_model_to_slug

_MPN_PATTERN = re.compile(r"\b([A-Z]{2,3}-[A-Z0-9-]{5,})\b")
_RTX_GTX_PATTERN = re.compile(
    r"\b(RTX|GTX)\s*(\d{4})(?:\s*(Ti|SUPER))?\b",
    re.IGNORECASE,
)
_RX_PATTERN = re.compile(r"\b(RX)\s*(\d{4})(?:\s*(XT|XTX))?\b", re.IGNORECASE)
_ARC_PATTERN = re.compile(r"\b(Arc)\s*([A-Za-z]\d+)\b", re.IGNORECASE)
_VRAM_PATTERN = re.compile(
    r"\b(\d{1,3})\s*(?:GB|G|기가)\b",
    re.IGNORECASE,
)


def _extract_brand(text: str) -> str | None:
    upper = text.upper()
    for brand in sorted(GPU_BOARD_PARTNERS, key=len, reverse=True):
        if brand in upper:
            return brand
    return None


def _extract_gpu_model(text: str) -> tuple[str | None, str | None]:
    match = _RTX_GTX_PATTERN.search(text)
    if match:
        series = match.group(1).upper()
        number = match.group(2)
        suffix = match.group(3)
        model = f"{series} {number}"
        if suffix:
            model = f"{model} {suffix.upper()}"
        return series, model

    match = _RX_PATTERN.search(text)
    if match:
        series = "RX"
        number = match.group(2)
        suffix = match.group(3)
        model = f"RX {number}"
        if suffix:
            model = f"{model} {suffix.upper()}"
        return series, model

    match = _ARC_PATTERN.search(text)
    if match:
        return "Arc", f"Arc {match.group(2).upper()}"

    return None, None


def _extract_vram_gb(text: str) -> int | None:
    matches = _VRAM_PATTERN.findall(text)
    if not matches:
        return None
    values = [int(value) for value in matches if value.isdigit()]
    return max(values) if values else None


def _extract_manufacturer_part_number(text: str) -> str | None:
    match = _MPN_PATTERN.search(text.upper())
    return match.group(1) if match else None


def has_gpu_keyword(text: str) -> bool:
    upper = text.upper()
    return any(keyword.upper() in upper for keyword in GPU_FILTER_KEYWORDS)


def parse_gpu(data: dict[str, Any]) -> dict[str, Any]:
    result = dict(data)
    source_text = (
        str(result.get("normalized_product_name"))
        or str(result.get("raw_product_name"))
        or str(result.get("product_name"))
        or ""
    )
    if not source_text:
        return result

    brand = _extract_brand(source_text)
    if brand:
        result["brand"] = brand
        result["board_partner_id"] = brand

    gpu_series, gpu_model = _extract_gpu_model(source_text)
    if gpu_series:
        result["gpu_series"] = gpu_series
    if gpu_model:
        result["gpu_model"] = gpu_model
        result["gpu_model_id"] = gpu_model_to_slug(gpu_model)

    vram = _extract_vram_gb(source_text)
    if vram is not None:
        result["vram_gb"] = vram

    mpn = _extract_manufacturer_part_number(source_text)
    if mpn:
        result["manufacturer_part_number"] = mpn

    return result
