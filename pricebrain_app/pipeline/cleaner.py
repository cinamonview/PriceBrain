"""Data cleaning — docs/08 §5."""

from __future__ import annotations

from typing import Any

from pricebrain_app.pipeline.utils import clean_string


def clean(data: dict[str, Any]) -> dict[str, Any]:
    """Remove whitespace/HTML entity noise before normalization."""
    result = dict(data)
    string_fields = (
        "mall",
        "product_id",
        "product_name",
        "brand",
        "brand_eng_nm",
        "manufacturer_part_number",
        "model_name",
        "seller",
        "product_url",
        "image_url",
    )
    for field in string_fields:
        if field in result and result[field] is not None:
            cleaned = clean_string(str(result[field]))
            result[field] = cleaned
    return result
