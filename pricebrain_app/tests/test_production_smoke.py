"""Production-like smoke gate tests — FakeFirestore / Mock HTTP only (no live Firebase)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from pricebrain_app.crawler.adapters.ssg import SSGCrawler, SSGHtmlFetcher
from pricebrain_app.crawler.client import IngestClient
from pricebrain_app.crawler.config import WorkerConfig
from pricebrain_app.crawler.http_client import HttpClient
from pricebrain_app.crawler.production_smoke import (
    SmokeConfig,
    SmokeExitCode,
    format_snapshot_block,
    render_smoke_outcome,
    run_smoke,
)
from pricebrain_app.crawler.results import CrawlerResult, CrawlerStatus
from pricebrain_app.crawler.scheduler import CrawlerScheduler
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.targets import CRAWL_STATUS_CLAIMED, CRAWLER_TARGETS_COLLECTION
from pricebrain_app.crawler.worker import CrawlerWorker
from pricebrain_app.tests.conftest import TEST_INGEST_API_KEY
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

FIXTURES = Path(__file__).parent / "fixtures" / "ssg"
NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
TARGET_ID = "ssg_1000832367906"
PRODUCT_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
OTHER_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000123456789"


@pytest.fixture
def smoke_db() -> FakeFirestoreClient:
    return FakeFirestoreClient()


@pytest.fixture
def smoke_repo(smoke_db: FakeFirestoreClient) -> CrawlTargetRepository:
    return CrawlTargetRepository(smoke_db)


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _make_due(repo: CrawlTargetRepository, url: str = PRODUCT_URL, *, enabled: bool = True) -> str:
    target = repo.upsert(mall_id="ssg", product_url=url, enabled=enabled, now=NOW)
    repo.update_after_crawl(
        target.target_id,
        result=CrawlerResult(status=CrawlerStatus.SUCCESS, mall_id="ssg"),
        next_crawl_at=NOW - timedelta(minutes=1),
        crawled_at=NOW - timedelta(hours=1),
    )
    return target.target_id


def _worker_factory(http_handler) -> callable:
    def factory(repo: CrawlTargetRepository) -> CrawlerWorker:
        def handler(request: httpx.Request) -> httpx.Response:
            return http_handler(request)

        http = HttpClient(
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            max_retries=0,
            sleep_func=lambda _: None,
        )
        scheduler = CrawlerScheduler(
            repo,
            crawler_factory=lambda: SSGCrawler(fetcher=SSGHtmlFetcher(http_client=http)),
        )
        return CrawlerWorker(
            repo,
            scheduler,
            owner_id="smoke-test-worker",
            config=WorkerConfig(max_targets_per_cycle=1, lease_seconds=120),
        )

    return factory


def _run(
    smoke_db: FakeFirestoreClient,
    *,
    target_id: str,
    ingest: bool = False,
    verify_firestore: bool = False,
    json_output: bool = False,
    worker_factory=None,
    ingest_client_factory=None,
) -> tuple:
    config = SmokeConfig(
        target_id=target_id,
        ingest=ingest,
        verify_firestore=verify_firestore,
        json_output=json_output,
        owner_id="smoke-test-worker",
    )
    outcome = run_smoke(
        config,
        db_factory=lambda: smoke_db,
        worker_factory=worker_factory,
        ingest_client_factory=ingest_client_factory,
        now=NOW,
    )
    rendered = render_smoke_outcome(
        outcome,
        verify_firestore=verify_firestore,
        json_output=json_output,
        secrets=[TEST_INGEST_API_KEY],
    )
    return outcome, rendered


def test_a_missing_target_exits_non_zero(smoke_db: FakeFirestoreClient, smoke_repo: CrawlTargetRepository) -> None:
    _ = smoke_repo
    outcome, _ = _run(smoke_db=smoke_db, target_id="ssg_missing")

    assert outcome.exit_code == SmokeExitCode.ERROR
    assert "Target not found" in outcome.message


def test_b_disabled_target_does_not_crawl(
    smoke_db: FakeFirestoreClient,
    smoke_repo: CrawlTargetRepository,
) -> None:
    target_id = _make_due(smoke_repo, enabled=False)

    outcome, _ = _run(
        smoke_db=smoke_db,
        target_id=target_id,
        worker_factory=_worker_factory(lambda _request: httpx.Response(200, text="")),
    )

    assert outcome.exit_code == SmokeExitCode.ERROR
    assert "disabled" in outcome.message.lower()
    assert outcome.crawl_result is None
    assert outcome.claimed is False


def test_c_active_lease_skips_crawl(
    smoke_db: FakeFirestoreClient,
    smoke_repo: CrawlTargetRepository,
) -> None:
    target_id = _make_due(smoke_repo)
    smoke_db.collection(CRAWLER_TARGETS_COLLECTION).document(target_id).set(
        {
            "crawl_status": CRAWL_STATUS_CLAIMED,
            "lease_owner": "other-worker",
            "lease_until": NOW + timedelta(minutes=5),
        },
        merge=True,
    )

    outcome, _ = _run(
        smoke_db=smoke_db,
        target_id=target_id,
        worker_factory=_worker_factory(lambda _request: httpx.Response(200, text="")),
    )

    assert outcome.exit_code == SmokeExitCode.SKIP
    assert "leased by another worker" in outcome.message
    assert outcome.crawl_result is None
    assert outcome.claimed is False


def test_d_http_403_records_ssg_access_denied_and_releases_lease(
    smoke_db: FakeFirestoreClient,
    smoke_repo: CrawlTargetRepository,
) -> None:
    target_id = _make_due(smoke_repo, OTHER_URL)

    def forbidden(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="denied", request=_request)

    outcome, rendered = _run(
        smoke_db=smoke_db,
        target_id=target_id,
        worker_factory=_worker_factory(forbidden),
        verify_firestore=True,
    )

    assert outcome.exit_code == SmokeExitCode.SUCCESS
    assert outcome.last_status == "HTTP_ERROR"
    assert outcome.error_code == "SSG_ACCESS_DENIED"
    assert outcome.lease_released is True
    assert "error_code: SSG_ACCESS_DENIED" in rendered


def test_e_success_updates_target_and_releases_lease(
    smoke_db: FakeFirestoreClient,
    smoke_repo: CrawlTargetRepository,
) -> None:
    target_id = _make_due(smoke_repo)
    html = _read_fixture("product_gpu.html")

    def ok(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, request=_request)

    outcome, _ = _run(
        smoke_db=smoke_db,
        target_id=target_id,
        worker_factory=_worker_factory(ok),
    )

    assert outcome.exit_code == SmokeExitCode.SUCCESS
    assert outcome.last_status == "SUCCESS"
    assert outcome.lease_released is True
    assert outcome.after is not None
    assert outcome.after.next_crawl_at == (NOW + timedelta(seconds=3600)).isoformat()
    assert outcome.after.last_crawled_price == 2_429_000


def test_f_without_ingest_does_not_create_ingest_client(
    smoke_db: FakeFirestoreClient,
    smoke_repo: CrawlTargetRepository,
) -> None:
    target_id = _make_due(smoke_repo)
    html = _read_fixture("product_gpu.html")
    ingest_factory = MagicMock(side_effect=AssertionError("IngestClient must not be created"))

    outcome, _ = _run(
        smoke_db=smoke_db,
        target_id=target_id,
        worker_factory=_worker_factory(lambda _request: httpx.Response(200, text=html, request=_request)),
        ingest_client_factory=ingest_factory,
    )

    assert outcome.exit_code == SmokeExitCode.SUCCESS
    assert outcome.ingest_attempted is False
    ingest_factory.assert_not_called()


def test_g_with_ingest_calls_ingest_client(
    smoke_db: FakeFirestoreClient,
    smoke_repo: CrawlTargetRepository,
) -> None:
    target_id = _make_due(smoke_repo)
    html = _read_fixture("product_gpu.html")
    ingest_client = MagicMock(spec=IngestClient)
    ingest_client.send_listing.return_value = {
        "product_id": "ZOTAC-RTX5080-16GB",
        "listing_id": TARGET_ID.replace("ssg_", "SSG_"),
        "price_history_appended": True,
    }

    outcome, _ = _run(
        smoke_db=smoke_db,
        target_id=target_id,
        ingest=True,
        worker_factory=_worker_factory(lambda _request: httpx.Response(200, text=html, request=_request)),
        ingest_client_factory=lambda: ingest_client,
    )

    assert outcome.exit_code == SmokeExitCode.SUCCESS
    assert outcome.ingest_attempted is True
    assert outcome.ingest_status == "SUCCESS"
    ingest_client.send_listing.assert_called_once()
    ingest_client.close.assert_called_once()


def test_h_verify_firestore_prints_before_and_after(
    smoke_db: FakeFirestoreClient,
    smoke_repo: CrawlTargetRepository,
) -> None:
    target_id = _make_due(smoke_repo)
    html = _read_fixture("product_gpu.html")

    outcome, rendered = _run(
        smoke_db=smoke_db,
        target_id=target_id,
        verify_firestore=True,
        worker_factory=_worker_factory(lambda _request: httpx.Response(200, text=html, request=_request)),
    )

    assert outcome.firestore_verified is True
    assert "========== BEFORE ==========" in rendered
    assert "========== AFTER ==========" in rendered
    assert format_snapshot_block("BEFORE", outcome.before) in rendered


def test_i_json_output_is_valid_and_contains_no_secrets(
    smoke_db: FakeFirestoreClient,
    smoke_repo: CrawlTargetRepository,
) -> None:
    target_id = _make_due(smoke_repo)
    html = _read_fixture("product_gpu.html")

    _, rendered = _run(
        smoke_db=smoke_db,
        target_id=target_id,
        json_output=True,
        worker_factory=_worker_factory(lambda _request: httpx.Response(200, text=html, request=_request)),
    )

    payload = json.loads(rendered)
    assert payload["target_id"] == target_id
    assert payload["last_status"] == "SUCCESS"
    assert TEST_INGEST_API_KEY not in rendered
    assert "Authorization" not in rendered
    assert "Bearer" not in rendered
