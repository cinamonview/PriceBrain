"""Crawler layer — SSOT: docs/07 (no Firestore, no Repository)."""

from pricebrain_app.crawler.malls.ssg import SsgCrawler, build_ssg_search_url
from pricebrain_app.crawler.types import RawProductData

__all__ = ["RawProductData", "SsgCrawler", "build_ssg_search_url"]
