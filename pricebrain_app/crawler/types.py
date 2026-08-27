"""RawProductData — docs/07 §3 (07 output / 08 input)."""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict


class RawProductData(TypedDict, total=False):
    """Fields per docs/07_CRAWLING_IMPLEMENTATION_DESIGN.md §3."""

    mall: str
    product_id: str
    product_name: str
    brand: str
    brand_eng_nm: str
    manufacturer_part_number: str
    model_name: str
    price: int | None
    seller: str
    product_url: str
    image_url: str
    availability: bool
    shipping_fee: int | None
    crawled_at: datetime | str
