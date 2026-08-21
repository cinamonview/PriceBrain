"""End-to-end crawler operational smoke tests — FakeFirestore and mocked HTTP only."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from pricebrain_app.crawler.adapters.ssg import SSGCrawler, SSGHtmlFetcher
from pricebrain_app.crawler.http_client import HttpClient
from pricebrain_app.crawler.results import CrawlerResult, CrawlerStatus
from pricebrain_app.crawler.scheduler import CrawlerScheduler
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.targets import CRAWL_STATUS_IDLE, CRAWLER_TARGETS_COLLECTION
from pricebrain_app.crawler.worker import CrawlerWorker, WorkerConfig
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

FIXTURES = Path(__file__).parent / "fixtures" / "ssg"
PRODUCT_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
TARGET_ID = "ssg_1000832367906"
NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def smoke_db() -> FakeFirestoreClient:
    return FakeFirestoreClient()


@pytest.fixture
def smoke_repo(smoke_db: FakeFirestoreClient) -> CrawlTargetRepository:
    return CrawlTargetRepository(smoke_db)


def _mock_crawler_factory() -> SSGCrawler:
    html = (FIXTURES / "product_gpu.html").read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, request=request)

    http = HttpClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep_func=lambda _: None,
    )
    return SSGCrawler(fetcher=SSGHtmlFetcher(http_client=http))


def test_crawler_operational_smoke_cycle(smoke_repo: CrawlTargetRepository) -> None:
    target = smoke_repo.upsert(
        mall_id="ssg",
        product_url=PRODUCT_URL,
        crawl_interval_seconds=3600,
        now=NOW,
    )
    assert target.target_id == TARGET_ID

    due = smoke_repo.list_due(NOW)
    assert [item.target_id for item in due] == [TARGET_ID]

    claimed = smoke_repo.try_claim(TARGET_ID, "smoke-worker", NOW, 300)
    assert claimed is not None
    assert claimed.lease_owner == "smoke-worker"

    scheduler = CrawlerScheduler(smoke_repo, crawler_factory=_mock_crawler_factory)
    worker = CrawlerWorker(
        smoke_repo,
        scheduler,
        owner_id="smoke-worker",
        config=WorkerConfig(max_targets_per_cycle=10),
    )
    result = worker.run_once(now=NOW)

    assert result.summary.success == 1
    saved = smoke_repo.get(TARGET_ID)
    assert saved is not None
    assert saved.last_status == "SUCCESS"
    assert saved.last_crawled_price == 2_429_000
    assert saved.next_crawl_at == NOW + timedelta(seconds=3600)
    assert saved.crawl_status == CRAWL_STATUS_IDLE
    assert saved.lease_owner is None
    assert saved.lease_until is None


def test_two_workers_cannot_claim_same_target(smoke_repo: CrawlTargetRepository) -> None:
    smoke_repo.upsert(mall_id="ssg", product_url=PRODUCT_URL, now=NOW)

    first = smoke_repo.try_claim(TARGET_ID, "worker-a", NOW, 300)
    second = smoke_repo.try_claim(TARGET_ID, "worker-b", NOW, 300)

    assert first is not None
    assert first.lease_owner == "worker-a"
    assert second is None


def test_expired_lease_can_be_reclaimed(
    smoke_repo: CrawlTargetRepository,
    smoke_db: FakeFirestoreClient,
) -> None:
    smoke_repo.upsert(mall_id="ssg", product_url=PRODUCT_URL, now=NOW)
    smoke_repo.try_claim(TARGET_ID, "worker-a", NOW, 300)
    smoke_db.collection(CRAWLER_TARGETS_COLLECTION).document(TARGET_ID).set(
        {"lease_until": NOW - timedelta(seconds=1)},
        merge=True,
    )

    reclaimed = smoke_repo.try_claim(TARGET_ID, "worker-b", NOW, 300)

    assert reclaimed is not None
    assert reclaimed.lease_owner == "worker-b"


def test_smoke_http_403_records_target_state(smoke_repo: CrawlTargetRepository) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="denied", request=request)

    http = HttpClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep_func=lambda _: None,
    )
    scheduler = CrawlerScheduler(
        smoke_repo,
        crawler_factory=lambda: SSGCrawler(fetcher=SSGHtmlFetcher(http_client=http)),
    )
    worker = CrawlerWorker(
        smoke_repo,
        scheduler,
        owner_id="smoke-worker",
        config=WorkerConfig(max_targets_per_cycle=10),
    )

    smoke_repo.upsert(mall_id="ssg", product_url=PRODUCT_URL, now=NOW)
    smoke_repo.update_after_crawl(
        TARGET_ID,
        result=CrawlerResult(status=CrawlerStatus.SUCCESS, mall_id="ssg"),
        next_crawl_at=NOW - timedelta(minutes=1),
        crawled_at=NOW - timedelta(hours=1),
    )

    result = worker.run_once(now=NOW)

    assert result.summary.http_error == 1
    saved = smoke_repo.get(TARGET_ID)
    assert saved is not None
    assert saved.last_status == "HTTP_ERROR"
    assert saved.last_error_code == "SSG_ACCESS_DENIED"
    assert saved.crawl_status == CRAWL_STATUS_IDLE
    assert saved.lease_owner is None
    assert saved.next_crawl_at == NOW + timedelta(seconds=3600)
