"""11번가 search JSON parser — search API payload → RawProductData.

11번가 PC search renders client-side, so there is no server-rendered product list
to scrape. The SPA calls a JSON endpoint (see malls.elevenst) whose response holds
several display collections, each with an `items` array. This module flattens those
into the existing docs/07 §3 RawProductData contract so the normal
parser → matcher → validator → repository path is reused unchanged.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pricebrain_app.crawler.malls.elevenst import build_elevenst_product_url
from pricebrain_app.crawler.types import RawProductData

DEFAULT_SELLER = "11번가"


def _first_price(item: dict[str, Any]) -> int | None:
    """Prefer the actually payable price; fall back to list price."""
    for field in ("finalPrc", "selPrc"):
        value = item.get(field)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            digits = value.replace(",", "").strip()
            if digits.isdigit():
                return int(digits)
    return None


def _item_to_raw(
    item: dict[str, Any],
    *,
    mall: str,
    crawled_at: datetime,
) -> RawProductData | None:
    product_id = str(item.get("id") or "").strip()
    title = str(item.get("title") or "").strip()
    if not product_id.isdigit() or not title:
        return None

    price = _first_price(item)
    if price is None or price <= 0:
        return None

    seller = str(item.get("sellerNickName") or "").strip() or DEFAULT_SELLER

    raw: RawProductData = {
        "mall": mall,
        "product_id": product_id,
        "product_name": title,
        "price": price,
        "seller": seller,
        "product_url": build_elevenst_product_url(product_id),
        "crawled_at": crawled_at,
    }

    image_url = item.get("imageUrl")
    if isinstance(image_url, str) and image_url.strip():
        raw["image_url"] = image_url.strip()

    sold_out = item.get("isSoldOut")
    if sold_out is None:
        sold_out = item.get("soldOut")
    if isinstance(sold_out, bool):
        raw["availability"] = not sold_out

    brand_eng = item.get("brandEngNm")
    if isinstance(brand_eng, str) and brand_eng.strip():
        raw["brand_eng_nm"] = brand_eng.strip()

    return raw


def parse_elevenst_search_json(
    payload: dict[str, Any],
    *,
    mall: str = "ELEVENST",
    crawled_at: datetime | None = None,
) -> list[RawProductData]:
    """Flatten every search collection into RawProductData, deduped by product id.

    Malformed items are skipped rather than raised: one bad row in a search page
    must never discard the rest of the page.
    """
    if not isinstance(payload, dict):
        return []

    collected_at = crawled_at or datetime.now(timezone.utc)
    seen: set[str] = set()
    results: list[RawProductData] = []

    for block in payload.get("data") or []:
        if not isinstance(block, dict):
            continue
        items = block.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            raw = _item_to_raw(item, mall=mall, crawled_at=collected_at)
            if raw is None:
                continue
            product_id = str(raw["product_id"])
            if product_id in seen:
                continue
            seen.add(product_id)
            results.append(raw)

    return results


def elevenst_search_total_pages(payload: dict[str, Any]) -> int | None:
    """Total page count reported by the search API, when present."""
    value = payload.get("totalPage") if isinstance(payload, dict) else None
    return value if isinstance(value, int) and value >= 0 else None
