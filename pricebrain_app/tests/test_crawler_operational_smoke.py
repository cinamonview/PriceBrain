"""Crawler operational verification gate — FakeFirestore and mocked HTTP only."""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from pricebrain_app.crawler.adapters.ssg import SSGCrawler, SSGHtmlFetcher
from pricebrain_app.crawler.client import IngestClient
from pricebrain_app.crawler.config import WorkerConfig
from pricebrain_app.crawler.exceptions import IngestClientHTTPError
from pricebrain_app.crawler.http_client import HttpClient
from pricebrain_app.crawler.results import CrawlerResult, CrawlerStatus
from pricebrain_app.crawler.scheduler import CrawlerScheduler
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.targets import CRAWL_STATUS_CLAIMED, CRAWL_STATUS_IDLE, CRAWLER_TARGETS_COLLECTION
from pricebrain_app.crawler.worker import CrawlerWorker, GracefulShutdown
from pricebrain_app.scripts import register_crawl_target, run_crawler_scheduler, run_crawler_worker
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

FIXTURES = Path(__file__).parent / "fixtures" / "ssg"
NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)

URL_SUCCESS_A = "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
URL_SUCCESS_B = "https://www.ssg.com/item/itemView.ssg?itemId=7777777777777"
URL_FORBIDDEN = "https://www.ssg.com/item/itemView.ssg?itemId=1000123456789"
URL_PARSE_FAIL = "https://www.ssg.com/item/itemView.ssg?itemId=9999999999999"
URL_TIMEOUT = "https://www.ssg.com/item/itemView.ssg?itemId=8888888888888"

TARGET_SUCCESS_A = "ssg_1000832367906"
TARGET_SUCCESS_B = "ssg_7777777777777"
TARGET_FORBIDDEN = "ssg_1000123456789"
TARGET_PARSE_FAIL = "ssg_9999999999999"
TARGET_TIMEOUT = "ssg_8888888888888"


@pytest.fixture
def gate_db() -> FakeFirestoreClient:
    return FakeFirestoreClient()


@pytest.fixture
def gate_repo(gate_db: FakeFirestoreClient) -> CrawlTargetRepository:
    return CrawlTargetRepository(gate_db)


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _make_due(
    repo: CrawlTargetRepository,
    url: str,
    *,
    enabled: bool = True,
) -> str:
    target = repo.upsert(mall_id="ssg", product_url=url, enabled=enabled, now=NOW)
    repo.update_after_crawl(
        target.target_id,
        result=CrawlerResult(status=CrawlerStatus.SUCCESS, mall_id="ssg"),
        next_crawl_at=NOW - timedelta(minutes=1),
        crawled_at=NOW - timedelta(hours=1),
    )
    return target.target_id


def _gate_crawler_factory() -> SSGCrawler:
    html = _read_fixture("product_gpu.html")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "1000123456789" in url:
            return httpx.Response(403, text="denied", request=request)
        if "9999999999999" in url:
            return httpx.Response(200, text="<html></html>", request=request)
        if "8888888888888" in url:
            raise httpx.TimeoutException("timed out", request=request)
        return httpx.Response(200, text=html, request=request)

    http = HttpClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0,
        sleep_func=lambda _: None,
    )
    return SSGCrawler(fetcher=SSGHtmlFetcher(http_client=http))


def _gate_worker(
    repo: CrawlTargetRepository,
    *,
    owner_id: str = "gate-worker",
    scheduler: CrawlerScheduler | None = None,
    shutdown: GracefulShutdown | None = None,
    sleep_fn=None,
) -> CrawlerWorker:
    return CrawlerWorker(
        repo,
        scheduler or CrawlerScheduler(repo, crawler_factory=_gate_crawler_factory),
        owner_id=owner_id,
        config=WorkerConfig(
            enabled=True,
            poll_interval_seconds=0.01,
            max_targets_per_cycle=10,
            lease_seconds=300,
        ),
        shutdown=shutdown,
        sleep_func=sleep_fn or (lambda _: None),
    )


# --- Smoke A: due target execution ---


def test_smoke_a_due_target_claim_crawl_release(gate_repo: CrawlTargetRepository) -> None:
    target_id = _make_due(gate_repo, URL_SUCCESS_A)
    worker = _gate_worker(gate_repo)

    result = worker.run_once(now=NOW)

    assert len(result.claimed_targets) == 1
    assert result.claimed_targets[0].target_id == target_id
    assert result.summary.success == 1
    saved = gate_repo.get(target_id)
    assert saved is not None
    assert saved.last_status == "SUCCESS"
    assert saved.last_crawled_price == 2_429_000
    assert saved.next_crawl_at == NOW + timedelta(seconds=3600)
    assert saved.crawl_status == CRAWL_STATUS_IDLE
    assert saved.lease_owner is None
    assert saved.lease_until is None


# --- Smoke B: active lease blocks second worker ---


def test_smoke_b_active_lease_blocks_worker_and_ingest(
    gate_repo: CrawlTargetRepository,
    gate_db: FakeFirestoreClient,
) -> None:
    target_id = _make_due(gate_repo, URL_SUCCESS_A)
    gate_db.collection(CRAWLER_TARGETS_COLLECTION).document(target_id).set(
        {
            "crawl_status": CRAWL_STATUS_CLAIMED,
            "lease_owner": "worker-a",
            "lease_until": NOW + timedelta(seconds=300),
        },
        merge=True,
    )

    ingest_client = MagicMock(spec=IngestClient)
    worker_b = _gate_worker(gate_repo, owner_id="worker-b")
    result = worker_b.run_once(ingest=True, ingest_client=ingest_client, now=NOW)

    assert result.claimed_targets == []
    assert result.skipped_targets == 1
    assert result.summary.total == 0
    ingest_client.send_listing.assert_not_called()


# --- Smoke C: expired lease reclaim ---


def test_smoke_c_expired_lease_is_reclaimed(
    gate_repo: CrawlTargetRepository,
    gate_db: FakeFirestoreClient,
) -> None:
    target_id = _make_due(gate_repo, URL_SUCCESS_A)
    gate_db.collection(CRAWLER_TARGETS_COLLECTION).document(target_id).set(
        {
            "crawl_status": CRAWL_STATUS_CLAIMED,
            "lease_owner": "dead-worker",
            "lease_until": NOW - timedelta(seconds=1),
        },
        merge=True,
    )

    worker = _gate_worker(gate_repo, owner_id="worker-b")
    result = worker.run_once(now=NOW)

    assert len(result.claimed_targets) == 1
    assert result.summary.success == 1
    saved = gate_repo.get(target_id)
    assert saved is not None
    assert saved.lease_owner is None
    assert saved.crawl_status == CRAWL_STATUS_IDLE


# --- Smoke D: failure isolation across five targets ---


def test_smoke_d_failure_isolation_does_not_stop_cycle(gate_repo: CrawlTargetRepository) -> None:
    ids = [
        _make_due(gate_repo, URL_SUCCESS_A),
        _make_due(gate_repo, URL_FORBIDDEN),
        _make_due(gate_repo, URL_PARSE_FAIL),
        _make_due(gate_repo, URL_TIMEOUT),
        _make_due(gate_repo, URL_SUCCESS_B),
    ]
    worker = _gate_worker(gate_repo)

    result = worker.run_once(now=NOW)

    assert result.summary.total == 5
    assert result.summary.success == 2
    assert result.summary.http_error == 1
    assert result.summary.parse_error == 1
    assert result.summary.timeout == 1

    assert gate_repo.get(ids[0]).last_status == "SUCCESS"
    forbidden = gate_repo.get(ids[1])
    assert forbidden is not None
    assert forbidden.last_status == "HTTP_ERROR"
    assert forbidden.last_error_code == "SSG_ACCESS_DENIED"
    assert gate_repo.get(ids[2]).last_status == "PARSE_ERROR"
    assert gate_repo.get(ids[3]).last_status == "TIMEOUT"
    assert gate_repo.get(ids[4]).last_status == "SUCCESS"


# --- Smoke E: ingest failure isolation ---


def test_smoke_e_ingest_500_isolated_and_cycle_continues(gate_repo: CrawlTargetRepository) -> None:
    first_id = _make_due(gate_repo, URL_SUCCESS_A)
    second_id = _make_due(gate_repo, URL_SUCCESS_B)

    ingest_client = MagicMock(spec=IngestClient)
    ingest_client.send_listing.side_effect = [
        IngestClientHTTPError("500", status_code=500, detail="server error"),
        {"listing_id": "listing-1"},
    ]

    worker = _gate_worker(gate_repo)
    result = worker.run_once(ingest=True, ingest_client=ingest_client, now=NOW)

    assert result.summary.total == 2
    assert result.summary.ingest_error == 1
    assert result.summary.success == 1
    assert ingest_client.send_listing.call_count == 2

    first = gate_repo.get(first_id)
    second = gate_repo.get(second_id)
    assert first is not None
    assert second is not None
    assert first.last_status == "INGEST_ERROR"
    assert first.lease_owner is None
    assert first.next_crawl_at == NOW + timedelta(seconds=3600)
    assert second.last_status == "SUCCESS"
    assert second.lease_owner is None


# --- Smoke F: graceful shutdown ---


def test_smoke_f_shutdown_prevents_new_claims_before_cycle(gate_repo: CrawlTargetRepository) -> None:
    shutdown = GracefulShutdown()
    shutdown.request_stop()
    _make_due(gate_repo, URL_SUCCESS_A)
    _make_due(gate_repo, URL_SUCCESS_B)

    worker = _gate_worker(gate_repo, shutdown=shutdown)
    result = worker.run_once(now=NOW)

    assert result.claimed_targets == []
    assert result.summary.total == 0
    assert result.shutdown_requested is True


def test_smoke_f_shutdown_stops_after_current_cycle(gate_repo: CrawlTargetRepository) -> None:
    shutdown = GracefulShutdown()
    sleeps: list[float] = []

    def sleep_fn(seconds: float) -> None:
        sleeps.append(seconds)
        shutdown.request_stop()

    _make_due(gate_repo, URL_SUCCESS_A)
    worker = _gate_worker(gate_repo, shutdown=shutdown, sleep_fn=sleep_fn)

    worker.run_forever(now=NOW)

    assert shutdown.should_stop is True
    assert len(sleeps) == 1


# --- Scheduler vs Worker boundary ---


def test_boundary_scheduler_has_no_run_forever() -> None:
    assert not hasattr(CrawlerScheduler, "run_forever")


def test_boundary_scheduler_run_once_has_no_infinite_loop() -> None:
    source = inspect.getsource(CrawlerScheduler.run_once)
    assert "while True" not in source
    assert "while not" not in source


def test_boundary_worker_delegates_due_selection_to_scheduler(
    gate_repo: CrawlTargetRepository,
) -> None:
    scheduler = MagicMock(spec=CrawlerScheduler)
    scheduler.get_due_targets.return_value = []
    scheduler.run_target_batch.return_value = ([], MagicMock(total=0))

    worker = CrawlerWorker(
        gate_repo,
        scheduler,
        owner_id="boundary-worker",
        config=WorkerConfig(enabled=True),
    )
    worker.run_once(now=NOW)

    scheduler.get_due_targets.assert_called_once()
    scheduler.run_target_batch.assert_not_called()


# --- CLI smoke ---


@pytest.mark.parametrize(
    ("module", "argv"),
    [
        (register_crawl_target, ["--help"]),
        (run_crawler_scheduler, ["--help"]),
        (run_crawler_worker, ["--help"]),
    ],
)
def test_cli_help_parses(module, argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        module.main(argv)
    assert exc.value.code == 0


def test_cli_worker_once_exits_zero_when_no_due_targets(
    gate_db: FakeFirestoreClient,
) -> None:
    with patch(
        "pricebrain_app.scripts.run_crawler_worker.get_firestore_client",
        return_value=gate_db,
    ):
        exit_code = run_crawler_worker.main(["--once"])

    assert exit_code == 0


# --- Production safety (gate) ---


def test_gate_no_hardcoded_production_ingest_api_key() -> None:
    forbidden = "pricebrain-test-key-2026"
    project_root = Path(__file__).resolve().parents[2]
    for path in project_root.rglob("*.py"):
        if path.name.endswith(".pyc"):
            continue
        if "test_crawler_operational_smoke.py" in str(path):
            continue
        text = path.read_text(encoding="utf-8")
        assert forbidden not in text, f"hardcoded ingest key found in {path}"
