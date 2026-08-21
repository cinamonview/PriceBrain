"""SSG HTML parser — docs/07 §6–§7."""

from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup, Tag

from pricebrain_app.crawler.parser.price import parse_price_attribute
from pricebrain_app.crawler.types import RawProductData

SSG_UNIT_SELECTOR = ".ssgitem_unit"


def parse_ssg_product_unit(
    unit: Tag,
    *,
    mall: str = "SSG",
    crawled_at: datetime | None = None,
) -> RawProductData | None:
    """Parse one SSG search-result unit into RawProductData."""
    product_id = unit.get("data-react-unit-id")
    if not product_id:
        return None

    name_tag = unit.select_one(".ssgitem_tit_name")
    product_name = name_tag.get_text(strip=True) if name_tag else None
    if not product_name:
        return None

    price = parse_price_attribute(unit.get("data-react-unit-price"))

    seller_tag = unit.select_one(".ssgitem_tit_brand")
    seller = seller_tag.get_text(strip=True) if seller_tag else None

    link_tag = unit.select_one(".ssgitem_info")
    product_url = link_tag.get("href") if link_tag else None

    image_tag = unit.select_one(".ssgitem_thmb_img")
    image_url = image_tag.get("src") if image_tag else None

    collected_at = crawled_at or datetime.now(timezone.utc)

    item: RawProductData = {
        "mall": mall,
        "product_id": str(product_id),
        "product_name": product_name,
        "price": price,
        "crawled_at": collected_at,
    }
    if seller:
        item["seller"] = seller
    if product_url:
        item["product_url"] = str(product_url)
    if image_url:
        item["image_url"] = str(image_url)
    return item


def parse_ssg_search_html(
    html: str,
    *,
    mall: str = "SSG",
    crawled_at: datetime | None = None,
) -> list[RawProductData]:
    """Parse SSG search/list HTML containing one or more product units."""
    soup = BeautifulSoup(html, "html.parser")
    units = soup.select(SSG_UNIT_SELECTOR)
    if not units:
        return []

    collected_at = crawled_at or datetime.now(timezone.utc)
    results: list[RawProductData] = []
    for unit in units:
        if not isinstance(unit, Tag):
            continue
        parsed = parse_ssg_product_unit(unit, mall=mall, crawled_at=collected_at)
        if parsed is not None:
            results.append(parsed)
    return results


def parse_ssg_product_html(html: str, *, mall: str = "SSG") -> RawProductData | None:
    """Parse HTML containing a single SSG product unit."""
    items = parse_ssg_search_html(html, mall=mall)
    return items[0] if items else None
