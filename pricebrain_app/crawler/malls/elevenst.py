"""11번가(ELEVENST) mall helpers — product URL validation, search URL build."""

from __future__ import annotations

import re
from urllib.parse import quote, urlparse

ELEVENST_PRODUCT_HOSTS = ("11st.co.kr", "www.11st.co.kr", "m.11st.co.kr")
ELEVENST_PRODUCT_PATH = re.compile(r"^/products/(?P<product_id>\d+)/?$")

# 11번가 PC search is a client-rendered SPA; the product list only exists in the
# JSON endpoint the SPA itself calls. Discovered from the search app bundle.
ELEVENST_SEARCH_API_URL = "https://apis.11st.co.kr/search/api/tab"
ELEVENST_PRODUCT_URL_TEMPLATE = "https://www.11st.co.kr/products/{product_id}"


def validate_elevenst_product_url(url: str) -> str:
    """Validate that a URL targets an 11번가 product detail page."""
    cleaned = url.strip()
    if not cleaned:
        raise ValueError("11번가 product URL is required")
    parsed = urlparse(cleaned)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid 11번가 product URL scheme: {url}")
    host = (parsed.hostname or "").lower()
    if host not in ELEVENST_PRODUCT_HOSTS:
        raise ValueError(f"URL is not an 11번가 product page: {url}")
    match = ELEVENST_PRODUCT_PATH.match(parsed.path or "")
    if not match:
        raise ValueError(f"URL is not an 11번가 product page: {url}")
    return cleaned


def extract_elevenst_product_id(url: str) -> str | None:
    """Extract product number from an 11번가 product URL."""
    parsed = urlparse(url.strip())
    match = ELEVENST_PRODUCT_PATH.match(parsed.path or "")
    if match:
        return match.group("product_id")
    return None


def build_elevenst_product_url(product_id: str) -> str:
    """Build a canonical 11번가 product URL from a product number.

    Search items carry an ad-tracking `linkUrl`; the product number is the only
    stable identity, so listing URLs are always rebuilt from it.
    """
    cleaned = str(product_id).strip()
    if not cleaned.isdigit():
        raise ValueError(f"11번가 product id must be numeric: {product_id!r}")
    return ELEVENST_PRODUCT_URL_TEMPLATE.format(product_id=cleaned)


def build_elevenst_search_url(keyword: str, *, page: int = 1) -> str:
    """Build the 11번가 search JSON URL for one keyword/page."""
    cleaned = keyword.strip()
    if not cleaned:
        raise ValueError("11번가 search keyword is required")
    if page < 1:
        raise ValueError(f"11번가 search page must be >= 1: {page}")
    return (
        f"{ELEVENST_SEARCH_API_URL}?poc=pc&tabId=TOTAL_SEARCH&tier=A"
        f"&searchKeyword={quote(cleaned, safe='')}&pageNo={page}"
    )
