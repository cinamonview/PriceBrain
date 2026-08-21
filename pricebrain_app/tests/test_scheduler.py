"""Crawler scheduler tests — due selection, run_once, ingest isolation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from pricebrain_app.crawler.adapters.ssg import SSGCrawler, SSGHtmlFetcher
from pricebrain_app.crawler.client import IngestClient
from pricebrain_app.crawler.http_client import HttpClient
from pricebrain_app.crawler.results import CrawlerResult, CrawlerStatus
from pricebrain_app.crawler.scheduler import CrawlerScheduler
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

FIXTURES = Path(__file__).parent / "fixtures" / "ssg"
PRODUCT_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
OTHER_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000123456789"
NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def scheduler_db() -> FakeFirestoreClient:
    return FakeFirestoreClient()


@pytest.fixture
def target_repo(scheduler_db: FakeFirestoreClient) -> CrawlTargetRepository:
    return CrawlTargetRepository(scheduler_db)


@pytest.fixture
def scheduler(target_repo: CrawlTargetRepository) -> CrawlerScheduler:
    return CrawlerScheduler(target_repo, crawler_factory=_mock_crawler_factory)


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _mock_crawler_factory() -> SSGCrawler:
    html = _read_fixture("product_gpu.html")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "1000123456789" in url:
            return httpx.Response(403, text="denied", request=request)
        if "9999999999999" in url:
            return httpx.Response(200, text="<html></html>", request=request)
        return httpx.Response(200, text=html, request=request)

    transport = httpx.MockTransport(handler)
    http = HttpClient(client=httpx.Client(transport=transport), sleep_func=lambda _: None)
    return SSGCrawler(fetcher=SSGHtmlFetcher(http_client=http))


def _register(
    repo: CrawlTargetRepository,
    url: str,
    *,
    enabled: bool = True,
    next_offset_seconds: int = -60,
) -> str:
    target = repo.upsert(mall_id="ssg", product_url=url, enabled=enabled, now=NOW)
    if next_offset_seconds != 0:
        repo.update_after_crawl(
            target.target_id,
            result=CrawlerResult(status=CrawlerStatus.SUCCESS, mall_id="ssg"),
            next_crawl_at=NOW + timedelta(seconds=next_offset_seconds),
            crawled_at=NOW - timedelta(hours=1),
        )
    return target.target_id


def test_get_due_targets_only_past_next_crawl_at(
    target_repo: CrawlTargetRepository,
    scheduler: CrawlerScheduler,
) -> None:
    due_id = _register(target_repo, PRODUCT_URL, next_offset_seconds=-60)
    future_id = _register(target_repo, OTHER_URL, next_offset_seconds=3600)

    due = scheduler.get_due_targets(NOW)
    assert [item.target_id for item in due] == [due_id]
    assert future_id not in {item.target_id for item in due}


def test_disabled_target_is_not_due(
    target_repo: CrawlTargetRepository,
    scheduler: CrawlerScheduler,
) -> None:
    _register(target_repo, PRODUCT_URL, enabled=False, next_offset_seconds=-60)
    assert scheduler.get_due_targets(NOW) == []


def test_run_once_updates_next_crawl_at_on_success(
    target_repo: CrawlTargetRepository,
    scheduler: CrawlerScheduler,
) -> None:
    target_id = _register(target_repo, PRODUCT_URL, next_offset_seconds=-60)

    run = scheduler.run_once(now=NOW)

    assert len(run.results) == 1
    assert run.results[0].status == CrawlerStatus.SUCCESS
    saved = target_repo.get(target_id)
    assert saved is not None
    assert saved.last_status == "SUCCESS"
    assert saved.next_crawl_at == NOW + timedelta(seconds=3600)
    assert saved.last_crawled_price == 2_429_000


@pytest.mark.parametrize(
    ("url", "expected_status"),
    [
        (OTHER_URL, CrawlerStatus.HTTP_ERROR),
        ("https://www.ssg.com/item/itemView.ssg?itemId=9999999999999", CrawlerStatus.PARSE_ERROR),
    ],
)
def test_run_once_updates_next_crawl_at_on_failure(
    url: str,
    expected_status: CrawlerStatus,
    target_repo: CrawlTargetRepository,
    scheduler: CrawlerScheduler,
) -> None:
    target_id = _register(target_repo, url, next_offset_seconds=-60)

    run = scheduler.run_once(now=NOW)

    assert run.results[0].status == expected_status
    saved = target_repo.get(target_id)
    assert saved is not None
    assert saved.last_status == expected_status.value
    assert saved.next_crawl_at == NOW + timedelta(seconds=3600)


def test_run_once_without_ingest_does_not_call_ingest_client(
    target_repo: CrawlTargetRepository,
    scheduler: CrawlerScheduler,
) -> None:
    _register(target_repo, PRODUCT_URL, next_offset_seconds=-60)
    ingest_client = MagicMock(spec=IngestClient)

    scheduler.run_once(now=NOW, ingest=False, ingest_client=ingest_client)

    ingest_client.send_listing.assert_not_called()


def test_run_once_with_ingest_calls_client(
    target_repo: CrawlTargetRepository,
    scheduler: CrawlerScheduler,
) -> None:
    _register(target_repo, PRODUCT_URL, next_offset_seconds=-60)
    ingest_client = MagicMock(spec=IngestClient)
    ingest_client.send_listing.return_value = {"status": "ok", "listing_id": "SSG_x"}

    run = scheduler.run_once(now=NOW, ingest=True, ingest_client=ingest_client)

    assert run.results[0].status == CrawlerStatus.SUCCESS
    ingest_client.send_listing.assert_called_once()


def test_run_once_filters_by_mall(
    target_repo: CrawlTargetRepository,
    scheduler: CrawlerScheduler,
) -> None:
    _register(target_repo, PRODUCT_URL, next_offset_seconds=-60)
    _register(target_repo, OTHER_URL, next_offset_seconds=-60)

    run = scheduler.run_once(now=NOW, mall_id="ssg")

    assert len(run.targets) == 2
    assert all(target.mall_id == "ssg" for target in run.targets)


def test_run_once_filters_by_target_id(
    target_repo: CrawlTargetRepository,
    scheduler: CrawlerScheduler,
) -> None:
    target_id = _register(target_repo, PRODUCT_URL, next_offset_seconds=-60)
    _register(target_repo, OTHER_URL, next_offset_seconds=-60)

    run = scheduler.run_once(now=NOW, target_id=target_id)

    assert len(run.targets) == 1
    assert run.targets[0].target_id == target_id


def test_calculate_next_run_adds_interval() -> None:
    scheduler = CrawlerScheduler(CrawlTargetRepository(FakeFirestoreClient()))
    next_run = scheduler.calculate_next_run(NOW, 3600, CrawlerStatus.HTTP_ERROR)
    assert next_run == NOW + timedelta(seconds=3600)


def _scheduler_with_factory(
    target_repo: CrawlTargetRepository,
    factory,
) -> CrawlerScheduler:
    return CrawlerScheduler(target_repo, crawler_factory=factory)


def test_run_once_updates_next_crawl_at_on_timeout(
    target_repo: CrawlTargetRepository,
) -> None:
    def timeout_factory() -> SSGCrawler:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("timed out", request=request)

        http = HttpClient(
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            max_retries=0,
            sleep_func=lambda _: None,
        )
        return SSGCrawler(fetcher=SSGHtmlFetcher(http_client=http))

    scheduler = _scheduler_with_factory(target_repo, timeout_factory)
    target_id = _register(target_repo, PRODUCT_URL, next_offset_seconds=-60)

    run = scheduler.run_once(now=NOW)

    assert run.results[0].status == CrawlerStatus.TIMEOUT
    saved = target_repo.get(target_id)
    assert saved is not None
    assert saved.last_status == "TIMEOUT"
    assert saved.next_crawl_at == NOW + timedelta(seconds=3600)


def test_run_once_updates_next_crawl_at_on_network_error(
    target_repo: CrawlTargetRepository,
) -> None:
    def network_factory() -> SSGCrawler:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection failed", request=request)

        http = HttpClient(
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            max_retries=0,
            sleep_func=lambda _: None,
        )
        return SSGCrawler(fetcher=SSGHtmlFetcher(http_client=http))

    scheduler = _scheduler_with_factory(target_repo, network_factory)
    target_id = _register(target_repo, PRODUCT_URL, next_offset_seconds=-60)

    run = scheduler.run_once(now=NOW)

    assert run.results[0].status == CrawlerStatus.NETWORK_ERROR
    saved = target_repo.get(target_id)
    assert saved is not None
    assert saved.last_status == "NETWORK_ERROR"
    assert saved.next_crawl_at == NOW + timedelta(seconds=3600)
