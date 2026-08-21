"""HTML parsers — docs/07."""

from pricebrain_app.crawler.parser.product import parse_product_html, parse_search_html
from pricebrain_app.crawler.parser.ssg import parse_ssg_product_html, parse_ssg_search_html

__all__ = [
    "parse_product_html",
    "parse_search_html",
    "parse_ssg_product_html",
    "parse_ssg_search_html",
]
