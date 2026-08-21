"""Product parser entrypoints — docs/07 §5."""

from __future__ import annotations

from pricebrain_app.crawler.parser.ssg import (
    parse_ssg_product_html,
    parse_ssg_search_html,
)
from pricebrain_app.crawler.types import RawProductData


def parse_product_html(html: str, mall: str) -> RawProductData | None:
    """Parse mall-specific product HTML into RawProductData."""
    if mall.upper() == "SSG":
        return parse_ssg_product_html(html, mall=mall)
    raise ValueError(f"Unsupported mall parser: {mall}")


def parse_search_html(html: str, mall: str) -> list[RawProductData]:
    """Parse mall-specific search-result HTML."""
    if mall.upper() == "SSG":
        return parse_ssg_search_html(html, mall=mall)
    raise ValueError(f"Unsupported mall parser: {mall}")
