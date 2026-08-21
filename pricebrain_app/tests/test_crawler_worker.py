"""Crawler worker operational tests — lease, filters, shutdown, failure isolation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from pricebrain_app.crawler.adapters.ssg import SSGCrawler, SSGHtmlFetcher
from pricebrain_app.crawler.client import IngestClient
from pricebrain_app.crawler.config import WorkerConfig, clear_crawler_config_cache
from pricebrain_app.crawler.http_client import HttpClient
from pricebrain_app.crawler.results import CrawlerResult, CrawlerStatus
from pricebrain_app.crawler.scheduler import CrawlerScheduler
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.targets import CRAWL_STATUS_CLAIMED, CRAWLER_TARGETS_COLLECTION, utc_now
from pricebrain_app.crawler.worker import CrawlerWorker, GracefulShutdown, generate_worker_owner_id
from pricebrain_app.scripts import run_crawler_worker
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

FIXTURES = Path(__file__).parent / "fixtures" / "ssg"
PRODUCT_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
OTHER_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000123456789"
NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def worker_db() -> FakeFirestoreClient:
    return FakeFirestoreClient()


@pytest.fixture
def target_repo(worker_db: FakeFirestoreClient) -> CrawlTargetRepository:
    return CrawlTargetRepository(worker_db)


@pytest.fixture
def scheduler(target_repo: CrawlTargetRepository) -> CrawlerScheduler:
    return CrawlerScheduler(target_repo, crawler_factory=_mock_crawler_factory)


@pytest.fixture
def worker(target_repo: CrawlTargetRepository, scheduler: CrawlerScheduler) -> CrawlerWorker:
    return CrawlerWorker(
        target_repo,
        scheduler,
        owner_id="test-worker",
        config=WorkerConfig(
            enabled=True,
            poll_interval_seconds=0.01,
            max_targets_per_cycle=10,
            lease_seconds=300,
        ),
    )


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


def _register_due(repo: CrawlTargetRepository, url: str, *, enabled: bool = True) -> str:
    target = repo.upsert(mall_id="ssg", product_url=url, enabled=enabled, now=NOW)
    repo.update_after_crawl(
        target.target_id,
        result=CrawlerResult(status=CrawlerStatus.SUCCESS, mall_id="ssg"),
        next_crawl_at=NOW - timedelta(minutes=1),
        crawled_at=NOW - timedelta(hours=1),
    )
    return target.target_id


def test_worker_once_runs_due_targets(worker: CrawlerWorker, target_repo: CrawlTargetRepository) -> None:
    target_id = _register_due(target_repo, PRODUCT_URL)

    result = worker.run_once(now=NOW)

    assert len(result.claimed_targets) == 1
    assert result.claimed_targets[0].target_id == target_id
    assert result.summary.success == 1
    saved = target_repo.get(target_id)
    assert saved is not None
    assert saved.lease_owner is None
    assert saved.last_status == "SUCCESS"


def test_worker_skips_disabled_target(
    worker: CrawlerWorker,
    target_repo: CrawlTargetRepository,
) -> None:
    _register_due(target_repo, PRODUCT_URL, enabled=False)

    result = worker.run_once(now=NOW)

    assert result.claimed_targets == []
    assert result.summary.total == 0


def test_worker_skips_not_due_target(
    worker: CrawlerWorker,
    target_repo: CrawlTargetRepository,
) -> None:
    target = target_repo.upsert(mall_id="ssg", product_url=PRODUCT_URL, now=NOW)
    target_repo.update_after_crawl(
        target.target_id,
        result=CrawlerResult(status=CrawlerStatus.SUCCESS, mall_id="ssg"),
        next_crawl_at=NOW + timedelta(hours=1),
        crawled_at=NOW,
    )

    result = worker.run_once(now=NOW)

    assert result.claimed_targets == []
    assert result.summary.total == 0


def test_worker_respects_max_targets(
    target_repo: CrawlTargetRepository,
    scheduler: CrawlerScheduler,
) -> None:
    limited_worker = CrawlerWorker(
        target_repo,
        scheduler,
        owner_id="test-worker",
        config=WorkerConfig(max_targets_per_cycle=1),
    )
    _register_due(target_repo, PRODUCT_URL)
    _register_due(target_repo, OTHER_URL)

    result = limited_worker.run_once(max_targets=1, now=NOW)

    assert len(result.claimed_targets) == 1
    assert result.summary.total == 1


def test_worker_filters_mall(
    worker: CrawlerWorker,
    target_repo: CrawlTargetRepository,
) -> None:
    _register_due(target_repo, PRODUCT_URL)

    result = worker.run_once(mall_id="ssg", now=NOW)

    assert result.summary.success == 1


def test_worker_filters_target_id(
    worker: CrawlerWorker,
    target_repo: CrawlTargetRepository,
) -> None:
    target_id = _register_due(target_repo, PRODUCT_URL)
    _register_due(target_repo, OTHER_URL)

    result = worker.run_once(target_id=target_id, now=NOW)

    assert len(result.claimed_targets) == 1
    assert result.claimed_targets[0].target_id == target_id


def test_one_target_failure_does_not_stop_worker(
    worker: CrawlerWorker,
    target_repo: CrawlTargetRepository,
) -> None:
    _register_due(target_repo, OTHER_URL)
    _register_due(target_repo, PRODUCT_URL)

    result = worker.run_once(now=NOW)

    assert result.summary.total == 2
    assert result.summary.success == 1
    assert result.summary.http_error == 1


def test_worker_claims_target(target_repo: CrawlTargetRepository) -> None:
    target_id = _register_due(target_repo, PRODUCT_URL)

    claimed = target_repo.try_claim(target_id, "worker-a", NOW, 300)

    assert claimed is not None
    assert claimed.lease_owner == "worker-a"
    assert claimed.crawl_status == CRAWL_STATUS_CLAIMED


def test_worker_skips_active_lease(
    worker: CrawlerWorker,
    target_repo: CrawlTargetRepository,
    worker_db: FakeFirestoreClient,
) -> None:
    target_id = _register_due(target_repo, PRODUCT_URL)
    worker_db.collection(CRAWLER_TARGETS_COLLECTION).document(target_id).set(
        {
            "crawl_status": CRAWL_STATUS_CLAIMED,
            "lease_owner": "other-worker",
            "lease_until": NOW + timedelta(minutes=5),
        },
        merge=True,
    )

    result = worker.run_once(now=NOW)

    assert result.claimed_targets == []
    assert result.skipped_targets == 1


def test_worker_can_reclaim_expired_lease(
    worker: CrawlerWorker,
    target_repo: CrawlTargetRepository,
    worker_db: FakeFirestoreClient,
) -> None:
    target_id = _register_due(target_repo, PRODUCT_URL)
    worker_db.collection(CRAWLER_TARGETS_COLLECTION).document(target_id).set(
        {
            "crawl_status": CRAWL_STATUS_CLAIMED,
            "lease_owner": "other-worker",
            "lease_until": NOW - timedelta(minutes=1),
        },
        merge=True,
    )

    result = worker.run_once(now=NOW)

    assert len(result.claimed_targets) == 1
    assert result.summary.success == 1


def test_worker_stops_cleanly(
    target_repo: CrawlTargetRepository,
    scheduler: CrawlerScheduler,
) -> None:
    shutdown = GracefulShutdown()
    sleeps: list[float] = []

    def sleep_fn(seconds: float) -> None:
        sleeps.append(seconds)
        shutdown.request_stop()

    worker = CrawlerWorker(
        target_repo,
        scheduler,
        owner_id="test-worker",
        config=WorkerConfig(poll_interval_seconds=0.01),
        shutdown=shutdown,
        sleep_func=sleep_fn,
    )
    _register_due(target_repo, PRODUCT_URL)

    worker.run_forever()

    assert shutdown.should_stop
    assert sleeps


def test_worker_once_without_ingest_does_not_call_client(
    worker: CrawlerWorker,
    target_repo: CrawlTargetRepository,
) -> None:
    _register_due(target_repo, PRODUCT_URL)
    ingest_client = MagicMock(spec=IngestClient)

    worker.run_once(ingest=False, ingest_client=ingest_client, now=NOW)

    ingest_client.send_listing.assert_not_called()


def test_worker_cli_once(
    worker_db: FakeFirestoreClient,
    target_repo: CrawlTargetRepository,
) -> None:
    _register_due(target_repo, PRODUCT_URL)

    with patch(
        "pricebrain_app.scripts.run_crawler_worker.get_firestore_client",
        return_value=worker_db,
    ):
        exit_code = run_crawler_worker.main(["--once"])

    assert exit_code == 0


def test_generate_worker_owner_id_is_stable_prefix() -> None:
    owner = generate_worker_owner_id()
    assert "-" in owner


def test_try_claim_release_roundtrip(target_repo: CrawlTargetRepository) -> None:
    target_id = _register_due(target_repo, PRODUCT_URL)
    claimed = target_repo.try_claim(target_id, "worker-a", NOW, 120)
    assert claimed is not None
    assert target_repo.try_claim(target_id, "worker-b", NOW, 120) is None
    assert target_repo.release_lease(target_id, "worker-a", now=NOW) is True
    reclaimed = target_repo.try_claim(target_id, "worker-b", NOW, 120)
    assert reclaimed is not None
    assert reclaimed.lease_owner == "worker-b"
