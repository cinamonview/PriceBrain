"""Mall-specific ingest adapters."""

from pricebrain_app.crawler.adapters.ssg import SSGCrawler, SSGHtmlFetcher, SSGProductParser

__all__ = ["SSGCrawler", "SSGHtmlFetcher", "SSGProductParser"]
