"""11번가 HTML parser — product detail pages."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from pricebrain_app.crawler.malls.elevenst import extract_elevenst_product_id
from pricebrain_app.crawler.parser.elevenst_mpn import extract_elevenst_detail_mpn
from pricebrain_app.crawler.parser.price import parse_price_text
from pricebrain_app.crawler.types import RawProductData

_BRACKET_PREFIX = re.compile(r"^\[[^\]]+\]\s*")
_PROPERTY_JSON = re.compile(
    r'property:\s*(\{"service_type".*?"is_adult_product":(?:true|false)\})',
    re.DOTALL,
)


def _strip_elevenst_title_prefix(name: str) -> str:
    return _BRACKET_PREFIX.sub("", name).strip()


def _parse_ld_json_product(soup: BeautifulSoup) -> dict | None:
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            payload = json.loads(raw.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("@type") == "Product":
            return payload
    return None


def _parse_property_json(html: str) -> dict | None:
    match = _PROPERTY_JSON.search(html)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _availability_from_offer(offer: dict | None) -> bool | None:
    if not offer:
        return None
    availability = str(offer.get("availability") or "")
    if "InStock" in availability:
        return True
    if "OutOfStock" in availability:
        return False
    return None


def parse_elevenst_product_detail_html(
    html: str,
    *,
    mall: str = "ELEVENST",
    product_url: str | None = None,
    crawled_at: datetime | None = None,
) -> RawProductData | None:
    """Parse 11번가 product detail HTML into RawProductData."""
    soup = BeautifulSoup(html, "html.parser")
    collected_at = crawled_at or datetime.now(timezone.utc)

    ld_product = _parse_ld_json_product(soup)
    property_data = _parse_property_json(html)

    product_name: str | None = None
    price: int | None = None
    product_id: str | None = None
    image_url: str | None = None
    seller: str | None = None
    availability: bool | None = None
    resolved_url = product_url

    if ld_product:
        product_name = str(ld_product.get("name") or "").strip() or None
        product_id = str(ld_product.get("productID") or "").strip() or None
        image = ld_product.get("image")
        if isinstance(image, str):
            image_url = image
        elif isinstance(image, list) and image:
            image_url = str(image[0])
        offer = ld_product.get("offers")
        if isinstance(offer, dict):
            raw_price = offer.get("price")
            if isinstance(raw_price, (int, float)):
                price = int(raw_price)
            elif raw_price is not None:
                price = parse_price_text(str(raw_price))
            if not resolved_url and offer.get("url"):
                resolved_url = str(offer["url"])
            availability = _availability_from_offer(offer)

    if property_data:
        if not product_name:
            product_name = str(property_data.get("product_name") or "").strip() or None
        if not product_id:
            product_id = str(property_data.get("product_no") or "").strip() or None
        if not image_url and property_data.get("product_image_url"):
            image_url = str(property_data["product_image_url"])
        if price is None and property_data.get("discount_price") is not None:
            price = int(property_data["discount_price"])
        if not seller and property_data.get("store_name"):
            seller = str(property_data["store_name"]).strip() or None
        if availability is None and "is_sale" in property_data:
            availability = bool(property_data["is_sale"])

    if not product_name:
        title_tag = soup.select_one("title")
        if title_tag:
            product_name = title_tag.get_text(strip=True) or None
    if product_name:
        product_name = _strip_elevenst_title_prefix(product_name)

    if price is None:
        meta_desc = soup.select_one('meta[name="description"]')
        if meta_desc and meta_desc.get("content"):
            match = re.search(r"할인모음가:\s*([\d,]+)", str(meta_desc["content"]))
            if match:
                price = parse_price_text(match.group(1))

    if not product_id:
        product_id = extract_elevenst_product_id(resolved_url or "")

    if not resolved_url:
        canonical = soup.select_one('link[rel="canonical"]')
        if canonical and canonical.get("href"):
            resolved_url = str(canonical["href"])

    if not seller:
        store_tag = soup.select_one(".c_product_store_title, .store_name")
        if store_tag:
            seller = store_tag.get_text(strip=True) or None
    if not seller:
        seller = "11번가"

    if not product_name or price is None or price <= 0 or not product_id or not resolved_url:
        return None

    manufacturer_part_number = extract_elevenst_detail_mpn(soup)

    item: RawProductData = {
        "mall": mall,
        "product_id": product_id,
        "product_name": product_name,
        "price": price,
        "crawled_at": collected_at,
        "seller": seller,
        "product_url": resolved_url,
    }
    if image_url:
        item["image_url"] = image_url
    if availability is not None:
        item["availability"] = availability
    if manufacturer_part_number:
        item["manufacturer_part_number"] = manufacturer_part_number
    return item
