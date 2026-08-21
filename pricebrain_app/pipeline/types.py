"""ValidatedProduct — 08 pipeline output (docs/08 §26)."""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict


class ValidatedProduct(TypedDict, total=False):
    mall: str
    mall_id: str
    product_id: str
    raw_product_name: str
    normalized_product_name: str
    brand: str
    board_partner_id: str
    gpu_series: str
    gpu_model: str
    gpu_model_id: str
    vram_gb: int
    manufacturer_part_number: str | None
    canonical_product_id: str
    price: int
    seller: str
    seller_id: str
    product_url: str
    image_url: str
    crawled_at: datetime
    availability: bool
    status: str
