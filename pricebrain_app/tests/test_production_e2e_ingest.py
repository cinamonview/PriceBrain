"""Production E2E ingest verification — FakeFirestore, Mock HTTP, TestClient only."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from pricebrain_app.api.deps import get_firestore
from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.crawler.adapters.ssg import SSGCrawler, SSGHtmlFetcher
from pricebrain_app.crawler.client import IngestClient
from pricebrain_app.crawler.config import WorkerConfig
from pricebrain_app.crawler.exceptions import IngestClientHTTPError
from pricebrain_app.crawler.http_client import HttpClient
from pricebrain_app.crawler.results import CrawlerResult, CrawlerStatus
from pricebrain_app.crawler.scheduler import CrawlerScheduler
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.targets import CRAWL_STATUS_IDLE
from pricebrain_app.crawler.worker import CrawlerWorker
from pricebrain_app.main import app
from pricebrain_app.repository import constants as c
from pricebrain_app.tests.conftest import TEST_INGEST_API_KEY
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient
from pricebrain_app.tests.test_crawler_ingest_e2e import _TestClientIngestBridge
from pricebrain_app.tests.test_repository import _history_count, _latest_history_price

FIXTURES = Path(__file__).parent / "fixtures" / "ssg"
PRODUCT_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
TARGET_ID = "ssg_1000832367906"
NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)

CANONICAL_PRODUCT_ID = "ZOTAC-RTX5080-16GB"
LISTING_ID = "SSG_test-rtx5080-001"
SSG_LISTING_ID = "SSG_1000832367906"


@pytest.fixture
def e2e_db() -> FakeFirestoreClient:
    from pricebrain_app.repository.gpu_master_seed import seed_gpu_master

    db = FakeFirestoreClient()
    seed_gpu_master(db)
    return db


@pytest.fixture
def ingest_bridge(
    e2e_db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> _TestClientIngestBridge:
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()

    def override_get_firestore():
        yield e2e_db

    app.dependency_overrides[get_firestore] = override_get_firestore
    bridge = _TestClientIngestBridge(TestClient(app), TEST_INGEST_API_KEY)
    yield bridge
    app.dependency_overrides.clear()
    clear_settings_cache()


def _product_count(db: FakeFirestoreClient) -> int:
    return sum(1 for path in db.paths() if path.startswith(f"{c.PRODUCTS}/"))


def _listing_count(db: FakeFirestoreClient) -> int:
    return sum(
        1
        for path in db.paths()
        if path.startswith(f"{c.LISTINGS}/") and f"/{c.PRICE_HISTORY}/" not in path
    )


def _zotac_payload(
    *,
    price: int,
    crawled_at: datetime,
) -> dict[str, Any]:
    return {
        "product_id": "test-rtx5080-001",
        "product_name": "ZOTAC GAMING GeForce RTX 5080 16GB",
        "mall_id": "ssg",
        "product_url": PRODUCT_URL,
        "price": price,
        "seller": "PriceBrain Test",
        "crawled_at": crawled_at.isoformat(),
    }


def _history_entries(db: FakeFirestoreClient, listing_id: str) -> list[dict[str, Any]]:
    prefix = f"{c.LISTINGS}/{listing_id}/{c.PRICE_HISTORY}/"
    entries: list[dict[str, Any]] = []
    for path in sorted(db.paths()):
        if not path.startswith(prefix):
            continue
        data = db.get_document(path)
        if data:
            entries.append(dict(data))
    return sorted(entries, key=lambda item: item["crawled_at"])


def _ingest(bridge: _TestClientIngestBridge, payload: dict[str, Any]) -> dict[str, Any]:
    result = bridge.send_listing(payload)
    assert result["status"] == "ok"
    return result


# --- Scenario A: first ingest ---


def test_scenario_a_first_ingest_creates_product_listing_and_history(
    e2e_db: FakeFirestoreClient,
    ingest_bridge: _TestClientIngestBridge,
) -> None:
    crawled_at = datetime(2026, 8, 21, 10, 0, 0, tzinfo=timezone.utc)
    result = _ingest(ingest_bridge, _zotac_payload(price=1_599_000, crawled_at=crawled_at))

    assert result["product_id"] == CANONICAL_PRODUCT_ID
    assert result["listing_id"] == LISTING_ID
    assert result["price_history_appended"] is True
    assert _product_count(e2e_db) == 1
    assert _listing_count(e2e_db) == 1
    assert e2e_db.get_document(f"{c.PRODUCTS}/{CANONICAL_PRODUCT_ID}") is not None
    assert e2e_db.get_document(f"{c.LISTINGS}/{LISTING_ID}") is not None
    assert _history_count(e2e_db, LISTING_ID) == 1


# --- Scenario B: same price re-ingest ---


def test_scenario_b_same_price_does_not_append_history(
    e2e_db: FakeFirestoreClient,
    ingest_bridge: _TestClientIngestBridge,
) -> None:
    first_at = datetime(2026, 8, 21, 10, 0, 0, tzinfo=timezone.utc)
    second_at = datetime(2026, 8, 21, 11, 0, 0, tzinfo=timezone.utc)

    _ingest(ingest_bridge, _zotac_payload(price=1_599_000, crawled_at=first_at))
    second = _ingest(ingest_bridge, _zotac_payload(price=1_599_000, crawled_at=second_at))

    assert second["price_history_appended"] is False
    assert _product_count(e2e_db) == 1
    assert _listing_count(e2e_db) == 1
    assert _history_count(e2e_db, LISTING_ID) == 1


# --- Scenario C: price change ---


def test_scenario_c_price_change_appends_history_with_previous_price(
    e2e_db: FakeFirestoreClient,
    ingest_bridge: _TestClientIngestBridge,
) -> None:
    first_at = datetime(2026, 8, 21, 10, 0, 0, tzinfo=timezone.utc)
    second_at = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)

    _ingest(ingest_bridge, _zotac_payload(price=1_599_000, crawled_at=first_at))
    third = _ingest(ingest_bridge, _zotac_payload(price=1_549_000, crawled_at=second_at))

    assert third["price_history_appended"] is True
    assert _history_count(e2e_db, LISTING_ID) == 2

    listing = e2e_db.get_document(f"{c.LISTINGS}/{LISTING_ID}")
    assert listing is not None
    assert int(listing["current_price"]) == 1_549_000

    history_prices = {int(entry["price"]) for entry in _history_entries(e2e_db, LISTING_ID)}
    assert history_prices == {1_599_000, 1_549_000}

    latest = _history_entries(e2e_db, LISTING_ID)[-1]
    assert int(latest["price"]) == 1_549_000
    assert int(latest["previous_price"]) == 1_599_000
    assert int(latest["price_change"]) == -50_000


# --- Scenario D: same changed price re-ingest ---


def test_scenario_d_same_changed_price_does_not_append_third_history(
    e2e_db: FakeFirestoreClient,
    ingest_bridge: _TestClientIngestBridge,
) -> None:
    times = [
        datetime(2026, 8, 21, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 21, 13, 0, 0, tzinfo=timezone.utc),
    ]
    _ingest(ingest_bridge, _zotac_payload(price=1_599_000, crawled_at=times[0]))
    _ingest(ingest_bridge, _zotac_payload(price=1_549_000, crawled_at=times[1]))
    fourth = _ingest(ingest_bridge, _zotac_payload(price=1_549_000, crawled_at=times[2]))

    assert fourth["price_history_appended"] is False
    assert _history_count(e2e_db, LISTING_ID) == 2
    listing = e2e_db.get_document(f"{c.LISTINGS}/{LISTING_ID}")
    assert listing is not None
    assert int(listing["current_price"]) == 1_549_000


# --- Scenario E: Worker → Crawl → Ingest E2E ---


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _make_due(repo: CrawlTargetRepository, url: str = PRODUCT_URL) -> str:
    target = repo.upsert(mall_id="ssg", product_url=url, now=NOW)
    repo.update_after_crawl(
        target.target_id,
        result=CrawlerResult(status=CrawlerStatus.SUCCESS, mall_id="ssg"),
        next_crawl_at=NOW - timedelta(minutes=1),
        crawled_at=NOW - timedelta(hours=1),
    )
    return target.target_id


def _worker_with_mock_html(
    repo: CrawlTargetRepository,
    html: str,
    *,
    ingest_client: IngestClient | None = None,
) -> CrawlerWorker:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, request=request)

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
        owner_id="e2e-worker",
        config=WorkerConfig(max_targets_per_cycle=1, lease_seconds=120),
    )


def test_scenario_e_worker_crawl_ingest_firestore_and_lease_release(
    e2e_db: FakeFirestoreClient,
    ingest_bridge: _TestClientIngestBridge,
) -> None:
    repo = CrawlTargetRepository(e2e_db)
    _make_due(repo)
    html = _read_fixture("product_detail_gpu.html")
    worker = _worker_with_mock_html(repo, html, ingest_client=ingest_bridge)  # type: ignore[arg-type]

    result = worker.run_once(
        ingest=True,
        target_id=TARGET_ID,
        ingest_client=ingest_bridge,  # type: ignore[arg-type]
        now=NOW,
    )

    assert len(result.claimed_targets) == 1
    assert result.summary.success == 1
    assert result.results[0].status == CrawlerStatus.SUCCESS
    assert result.results[0].ingest_response is not None
    assert result.results[0].ingest_response["listing_id"] == SSG_LISTING_ID

    saved = repo.get(TARGET_ID)
    assert saved is not None
    assert saved.last_status == "SUCCESS"
    assert saved.last_crawled_price == 1_599_000
    assert saved.crawl_status == CRAWL_STATUS_IDLE
    assert saved.lease_owner is None
    assert saved.next_crawl_at == NOW + timedelta(seconds=3600)

    assert e2e_db.get_document(f"{c.LISTINGS}/{SSG_LISTING_ID}") is not None
    assert _history_count(e2e_db, SSG_LISTING_ID) >= 1


# --- Scenario F: ingest failure isolation ---


def test_scenario_f_ingest_500_does_not_persist_listing_and_releases_lease(
    e2e_db: FakeFirestoreClient,
    ingest_bridge: _TestClientIngestBridge,
) -> None:
    repo = CrawlTargetRepository(e2e_db)
    first_id = _make_due(repo, PRODUCT_URL)
    second_id = _make_due(repo, "https://www.ssg.com/item/itemView.ssg?itemId=7777777777777")
    html = _read_fixture("product_detail_gpu.html")

    calls = {"n": 0}

    class _FailOnceIngestClient:
        def send_listing(self, payload: dict[str, Any]) -> dict[str, Any]:
            calls["n"] += 1
            if calls["n"] == 1:
                raise IngestClientHTTPError("500", status_code=500, detail="server error")
            return ingest_bridge.send_listing(payload)

        def close(self) -> None:
            return None

    failing_client = _FailOnceIngestClient()
    worker = _worker_with_mock_html(repo, html, ingest_client=failing_client)  # type: ignore[arg-type]
    listings_before = _listing_count(e2e_db)

    result = worker.run_once(
        ingest=True,
        max_targets=2,
        ingest_client=failing_client,  # type: ignore[arg-type]
        now=NOW,
    )

    assert result.summary.total == 2
    assert result.summary.ingest_error == 1
    assert result.summary.success == 1
    assert calls["n"] == 2
    assert _listing_count(e2e_db) == listings_before + 1
    listing_paths = [
        path
        for path in e2e_db.paths()
        if path.startswith(f"{c.LISTINGS}/") and f"/{c.PRICE_HISTORY}/" not in path
    ]
    assert len(listing_paths) == 1

    first = repo.get(first_id)
    second = repo.get(second_id)
    assert first is not None
    assert second is not None
    assert first.last_status == "INGEST_ERROR"
    assert first.lease_owner is None
    assert first.crawl_status == CRAWL_STATUS_IDLE
    assert second.last_status == "SUCCESS"
    assert second.lease_owner is None


def test_scenario_abcd_full_sequence_regression(
    e2e_db: FakeFirestoreClient,
    ingest_bridge: _TestClientIngestBridge,
) -> None:
    """Single regression covering A→B→C→D price history state machine."""
    t1 = datetime(2026, 8, 21, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 21, 11, 0, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
    t4 = datetime(2026, 8, 21, 13, 0, 0, tzinfo=timezone.utc)

    r1 = _ingest(ingest_bridge, _zotac_payload(price=1_599_000, crawled_at=t1))
    r2 = _ingest(ingest_bridge, _zotac_payload(price=1_599_000, crawled_at=t2))
    r3 = _ingest(ingest_bridge, _zotac_payload(price=1_549_000, crawled_at=t3))
    r4 = _ingest(ingest_bridge, _zotac_payload(price=1_549_000, crawled_at=t4))

    assert r1["price_history_appended"] is True
    assert r2["price_history_appended"] is False
    assert r3["price_history_appended"] is True
    assert r4["price_history_appended"] is False
    assert _product_count(e2e_db) == 1
    assert _listing_count(e2e_db) == 1
    assert _history_count(e2e_db, LISTING_ID) == 2
