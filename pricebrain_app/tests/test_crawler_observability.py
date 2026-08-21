"""Crawler operations and observability tests — FakeFirestore only."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.crawler.metrics import get_crawler_metrics, reset_crawler_metrics
from pricebrain_app.crawler.ops_format import (
    format_schedule,
    format_status_summary,
    format_target_detail,
)
from pricebrain_app.crawler.operations_view import CrawlerOperationsView, TargetListFilter
from pricebrain_app.crawler.results import CrawlerResult, CrawlerStatus
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.targets import CRAWL_STATUS_CLAIMED, CRAWLER_TARGETS_COLLECTION
from pricebrain_app.crawler.worker_health import get_worker_health, mark_cycle_finished, reset_worker_health
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.listing_repository import build_listing_document_id
from pricebrain_app.scripts import (
    crawler_schedule,
    crawler_status,
    list_crawl_targets,
    list_crawler_failures,
    show_crawl_target,
)
from pricebrain_app.tests.conftest import TEST_INGEST_API_KEY
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
PRODUCT_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
TARGET_A = "ssg_1000832367906"
TARGET_B = "ssg_7777777777777"
LISTING_A = build_listing_document_id("ssg", "1000832367906")


@pytest.fixture(autouse=True)
def _reset_observability_state() -> None:
    reset_crawler_metrics()
    reset_worker_health()
    yield
    reset_crawler_metrics()
    reset_worker_health()


@pytest.fixture
def ops_db() -> FakeFirestoreClient:
    return FakeFirestoreClient()


@pytest.fixture
def ops_repo(ops_db: FakeFirestoreClient) -> CrawlTargetRepository:
    return CrawlTargetRepository(ops_db)


@pytest.fixture
def ops_view(ops_db: FakeFirestoreClient, ops_repo: CrawlTargetRepository) -> CrawlerOperationsView:
    return CrawlerOperationsView(ops_repo, ops_db)


def _seed_targets(repo: CrawlTargetRepository, db: FakeFirestoreClient) -> None:
    repo.upsert(mall_id="ssg", product_url=PRODUCT_URL, enabled=True, now=NOW)
    repo.upsert(
        mall_id="ssg",
        product_url="https://www.ssg.com/item/itemView.ssg?itemId=7777777777777",
        enabled=False,
        now=NOW,
    )
    repo.update_after_crawl(
        TARGET_A,
        result=CrawlerResult(status=CrawlerStatus.HTTP_ERROR, mall_id="ssg", message="SSG_ACCESS_DENIED"),
        next_crawl_at=NOW + timedelta(hours=1),
        crawled_at=NOW - timedelta(minutes=10),
    )
    db.collection(CRAWLER_TARGETS_COLLECTION).document(TARGET_B).set({"last_status": "SUCCESS"}, merge=True)
    db.collection(CRAWLER_TARGETS_COLLECTION).document(TARGET_A).set(
        {
            "next_crawl_at": NOW - timedelta(minutes=5),
            "last_status": "HTTP_ERROR",
            "last_error_code": "SSG_ACCESS_DENIED",
            "last_error_message": "SSG_ACCESS_DENIED",
        },
        merge=True,
    )


def test_a_list_targets(ops_repo: CrawlTargetRepository, ops_view: CrawlerOperationsView, ops_db: FakeFirestoreClient) -> None:
    _seed_targets(ops_repo, ops_db)
    targets = ops_view.list_targets(now=NOW)
    assert len(targets) == 2
    assert {item.target_id for item in targets} == {TARGET_A, TARGET_B}


def test_b_enabled_disabled_filters(ops_view: CrawlerOperationsView, ops_repo: CrawlTargetRepository, ops_db: FakeFirestoreClient) -> None:
    _seed_targets(ops_repo, ops_db)
    enabled = ops_view.list_targets(filters=TargetListFilter(enabled=True), now=NOW)
    disabled = ops_view.list_targets(filters=TargetListFilter(enabled=False), now=NOW)
    assert len(enabled) == 1
    assert enabled[0].target_id == TARGET_A
    assert len(disabled) == 1
    assert disabled[0].target_id == TARGET_B


def test_c_due_filter(ops_view: CrawlerOperationsView, ops_repo: CrawlTargetRepository, ops_db: FakeFirestoreClient) -> None:
    _seed_targets(ops_repo, ops_db)
    due = ops_view.list_targets(filters=TargetListFilter(due_only=True), now=NOW)
    assert [item.target_id for item in due] == [TARGET_A]


def test_d_failed_filter(ops_view: CrawlerOperationsView, ops_repo: CrawlTargetRepository, ops_db: FakeFirestoreClient) -> None:
    _seed_targets(ops_repo, ops_db)
    failed = ops_view.list_targets(filters=TargetListFilter(failed_only=True), now=NOW)
    assert len(failed) == 1
    assert failed[0].last_error_code == "SSG_ACCESS_DENIED"


def test_e_recent_failures_sorted(ops_view: CrawlerOperationsView, ops_repo: CrawlTargetRepository, ops_db: FakeFirestoreClient) -> None:
    _seed_targets(ops_repo, ops_db)
    failures = ops_view.list_recent_failures(limit=10)
    assert len(failures) == 1
    assert failures[0].target_id == TARGET_A


def test_f_mall_filter(ops_view: CrawlerOperationsView, ops_repo: CrawlTargetRepository, ops_db: FakeFirestoreClient) -> None:
    _seed_targets(ops_repo, ops_db)
    targets = ops_view.list_targets(filters=TargetListFilter(mall_id="ssg"), now=NOW)
    assert len(targets) == 2
    assert all(item.mall_id == "ssg" for item in targets)


def test_g_crawler_status_summary(ops_view: CrawlerOperationsView, ops_repo: CrawlTargetRepository, ops_db: FakeFirestoreClient) -> None:
    _seed_targets(ops_repo, ops_db)
    summary = ops_view.summarize(now=NOW)
    assert summary.total_targets == 2
    assert summary.enabled_targets == 1
    assert summary.disabled_targets == 1
    assert summary.due_targets == 1
    assert summary.failed_targets == 1
    text = format_status_summary(summary, ops_view.summarize_by_mall(now=NOW))
    assert "PriceBrain Crawler Status" in text
    assert "Failed: 1" in text


def test_h_target_detail(ops_view: CrawlerOperationsView, ops_repo: CrawlTargetRepository, ops_db: FakeFirestoreClient) -> None:
    _seed_targets(ops_repo, ops_db)
    target = ops_view.get_target(TARGET_A, now=NOW)
    assert target is not None
    detail = format_target_detail(target)
    assert "SSG_ACCESS_DENIED" in detail
    assert "itemId=1000832367906" in detail


def test_i_price_history_read(ops_view: CrawlerOperationsView, ops_repo: CrawlTargetRepository, ops_db: FakeFirestoreClient) -> None:
    _seed_targets(ops_repo, ops_db)
    ops_db.collection(c.LISTINGS).document(LISTING_A).set(
        {
            "normalized_product_name": "ZOTAC RTX 5080",
            "current_price": 1_549_000,
            "crawled_at": NOW,
        }
    )
    ops_db.collection(c.LISTINGS).document(LISTING_A).collection(c.PRICE_HISTORY).document("1").set(
        {
            "price": 1_549_000,
            "previous_price": 1_599_000,
            "price_change": -50_000,
            "crawled_at": NOW,
        }
    )
    price_view = ops_view.get_price_change_for_target(TARGET_A)
    assert price_view is not None
    assert price_view.current_price == 1_549_000
    assert price_view.previous_price == 1_599_000
    assert price_view.price_change == -50_000


def test_j_json_output(ops_view: CrawlerOperationsView, ops_repo: CrawlTargetRepository, ops_db: FakeFirestoreClient) -> None:
    _seed_targets(ops_repo, ops_db)
    payload = ops_view.status_payload(now=NOW)
    text = json.dumps(payload, default=str)
    assert "summary" in text
    assert "worker_health" in text


def test_k_secret_masking_in_json_output(
    ops_view: CrawlerOperationsView,
    ops_repo: CrawlTargetRepository,
    ops_db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_targets(ops_repo, ops_db)
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()
    payload = ops_view.status_payload(now=NOW)
    text = json.dumps(payload, default=str)
    assert TEST_INGEST_API_KEY not in text
    assert "Authorization" not in text


def test_l_lease_state_display(ops_view: CrawlerOperationsView, ops_repo: CrawlTargetRepository, ops_db: FakeFirestoreClient) -> None:
    _seed_targets(ops_repo, ops_db)
    ops_db.collection(CRAWLER_TARGETS_COLLECTION).document(TARGET_A).set(
        {
            "crawl_status": CRAWL_STATUS_CLAIMED,
            "lease_owner": "worker-a",
            "lease_until": NOW + timedelta(minutes=5),
        },
        merge=True,
    )
    target = ops_view.get_target(TARGET_A, now=NOW)
    assert target is not None
    assert target.operational_state == "CLAIMED"
    assert target.has_active_lease is True
    detail = format_target_detail(target)
    assert "claimed by worker-a" in detail


def test_m_scheduler_next_crawl_display(
    ops_view: CrawlerOperationsView,
    ops_repo: CrawlTargetRepository,
    ops_db: FakeFirestoreClient,
) -> None:
    _seed_targets(ops_repo, ops_db)
    ops_db.collection(CRAWLER_TARGETS_COLLECTION).document(TARGET_A).set(
        {"next_crawl_at": NOW + timedelta(minutes=42)},
        merge=True,
    )
    entries = ops_view.list_schedule(now=NOW)
    assert len(entries) == 1
    assert entries[0].is_due is False
    assert entries[0].seconds_until_due == 42 * 60
    due_entries = [entry for entry in entries if entry.is_due]
    ops_db.collection(CRAWLER_TARGETS_COLLECTION).document(TARGET_A).set(
        {"next_crawl_at": NOW - timedelta(minutes=1)},
        merge=True,
    )
    due = ops_view.list_schedule(now=NOW)
    assert due[0].is_due is True
    assert "DUE" in format_schedule(due)


def test_n_worker_health_state() -> None:
    from pricebrain_app.crawler.results import CrawlerBatchSummary

    mark_cycle_finished(CrawlerBatchSummary(total=2, success=1, http_error=1))
    health = get_worker_health()
    assert health.last_cycle_total == 2
    assert health.last_cycle_success == 1
    assert health.last_cycle_failed == 1


def test_cli_help_parses() -> None:
    with pytest.raises(SystemExit) as exc:
        crawler_status.main(["--help"])
    assert exc.value.code == 0
    with pytest.raises(SystemExit):
        list_crawl_targets.main(["--help"])
    with pytest.raises(SystemExit):
        list_crawler_failures.main(["--help"])
    with pytest.raises(SystemExit):
        show_crawl_target.main(["--help"])
    with pytest.raises(SystemExit):
        crawler_schedule.main(["--help"])


def test_cli_list_and_show_with_fake_firestore(
    ops_db: FakeFirestoreClient,
    ops_repo: CrawlTargetRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_targets(ops_repo, ops_db)
    monkeypatch.setattr("pricebrain_app.crawler.ops_cli.get_firestore_client", lambda: ops_db)

    assert list_crawl_targets.main(["--failed"]) == 0
    assert list_crawler_failures.main(["--limit", "5"]) == 0
    assert show_crawl_target.main(["--target-id", TARGET_A]) == 0
    assert crawler_schedule.main([]) == 0
    assert crawler_status.main(["--json"]) == 0


def test_metrics_snapshot_available() -> None:
    metrics = get_crawler_metrics()
    assert metrics.crawl_attempts == 0
    assert "lease_claims" in metrics.to_dict()
