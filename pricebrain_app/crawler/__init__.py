"""Crawler layer — SSOT: docs/07 (no Firestore, no Repository)."""

from pricebrain_app.crawler.adapters.ssg import SSGCrawler, SSGHtmlFetcher, SSGProductParser
from pricebrain_app.crawler.base import BaseCrawler, BaseMallCrawler
from pricebrain_app.crawler.client import IngestClient
from pricebrain_app.crawler.malls.ssg import SsgCrawler, build_ssg_search_url
from pricebrain_app.crawler.models import IngestListingPayload, ingest_payload_from_raw
from pricebrain_app.crawler.results import CrawlerBatchSummary, CrawlerResult, CrawlerStatus
from pricebrain_app.crawler.scheduler import CrawlerScheduler, SchedulerRunResult
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.targets import CrawlTarget
from pricebrain_app.crawler.worker import CrawlerWorker, GracefulShutdown, WorkerRunResult
from pricebrain_app.crawler.test_crawler import TestCrawler
from pricebrain_app.crawler.types import RawProductData

__all__ = [
    "BaseCrawler",
    "BaseMallCrawler",
    "CrawlerBatchSummary",
    "CrawlerResult",
    "CrawlerScheduler",
    "CrawlerStatus",
    "CrawlTarget",
    "CrawlTargetRepository",
    "CrawlerWorker",
    "GracefulShutdown",
    "IngestClient",
    "IngestListingPayload",
    "RawProductData",
    "SchedulerRunResult",
    "WorkerRunResult",
    "SSGCrawler",
    "SSGHtmlFetcher",
    "SSGProductParser",
    "SsgCrawler",
    "TestCrawler",
    "build_ssg_search_url",
    "ingest_payload_from_raw",
]
