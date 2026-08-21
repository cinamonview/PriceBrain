"""SSG HTML parser — docs/07 §6–§7."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup, Tag

from pricebrain_app.crawler.parser.price import parse_price_attribute, parse_price_text
from pricebrain_app.crawler.types import RawProductData

SSG_UNIT_SELECTOR = ".ssgitem_unit"


def extract_ssg_item_id_from_url(url: str | None) -> str | None:
    """Extract SSG itemId from a product detail URL query string."""
    if not url:
        return None
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in ("itemId", "itemid"):
        values = query.get(key)
        if values and values[0]:
            return str(values[0]).strip()
    return None


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


def parse_ssg_product_detail_html(
    html: str,
    *,
    mall: str = "SSG",
    product_url: str | None = None,
    crawled_at: datetime | None = None,
) -> RawProductData | None:
    """Parse SSG product detail page HTML (itemView.ssg)."""
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.select_one(".cdtl_info_tit")
    product_name = title_tag.get_text(strip=True) if title_tag else None
    if not product_name:
        og_title = soup.select_one('meta[property="og:title"]')
        if og_title and og_title.get("content"):
            product_name = str(og_title["content"]).strip()
    if not product_name:
        return None

    price_tag = soup.select_one(".ssg_price")
    price = parse_price_text(price_tag.get_text() if price_tag else None)
    if price is None:
        sell_tag = soup.select_one("#sellprc")
        price = parse_price_text(sell_tag.get_text() if sell_tag else None)
    if price is None or price <= 0:
        return None

    product_id = extract_ssg_item_id_from_url(product_url)
    if not product_id:
        meta_item = soup.select_one('meta[property="rb:itemId"]')
        if meta_item and meta_item.get("content"):
            product_id = str(meta_item["content"]).strip()
    if not product_id:
        match = re.search(r"상품번호\s*[:：]?\s*(\d+)", soup.get_text())
        if match:
            product_id = match.group(1)
    if not product_id:
        return None

    seller_tag = soup.select_one(".cdtl_info_tit_brand")
    seller = seller_tag.get_text(strip=True) if seller_tag else None
    if not seller:
        brand_tag = soup.select_one(".cdtl_cmpt_brand_name")
        seller = brand_tag.get_text(strip=True) if brand_tag else None
    if not seller:
        return None

    resolved_url = product_url
    if not resolved_url:
        canonical = soup.select_one('link[rel="canonical"]')
        if canonical and canonical.get("href"):
            resolved_url = str(canonical["href"])
    if not resolved_url:
        return None

    image_tag = soup.select_one(".cdtl_img_view img, .cdtl_thmb img")
    image_url = image_tag.get("src") if image_tag else None

    collected_at = crawled_at or datetime.now(timezone.utc)

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
        item["image_url"] = str(image_url)
    return item


def parse_ssg_product_page_html(
    html: str,
    *,
    mall: str = "SSG",
    product_url: str | None = None,
    crawled_at: datetime | None = None,
) -> RawProductData | None:
    """Parse search-unit or product-detail HTML into one RawProductData."""
    search_items = parse_ssg_search_html(html, mall=mall, crawled_at=crawled_at)
    if search_items:
        item = dict(search_items[0])
        if product_url:
            item["product_url"] = product_url
        return item  # type: ignore[return-value]
    return parse_ssg_product_detail_html(
        html,
        mall=mall,
        product_url=product_url,
        crawled_at=crawled_at,
    )
