"""Regression tests for request-scoped Firestore read deduplication."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from pricebrain_app.crawler.alert_operations_view import AlertOperationsView
from pricebrain_app.crawler.audit_operations_view import AuditOperationsView
from pricebrain_app.crawler.command_center_operations_cli import build_command_center_operations_view
from pricebrain_app.crawler.command_center_operations_models import CommandCenterFilter
from pricebrain_app.crawler.investigation_operations_view import InvestigationOperationsView
from pricebrain_app.crawler.operations_view import CrawlerOperationsView
from pricebrain_app.crawler.operations_read_cache import operations_read_scope
from pricebrain_app.crawler.price_alert_models import PRICE_ALERTS_COLLECTION, PriceAlertType
from pricebrain_app.crawler.price_alert_repository import PriceAlertRepository
from pricebrain_app.crawler.price_operations_view import PriceOperationsView
from pricebrain_app.crawler.remediation_operations_view import RemediationOperationsView
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.listing_repository import build_listing_document_id
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
TARGET_ID = "ssg_1000832367906"
PRODUCT_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
LISTING_ID = build_listing_document_id("ssg", "1000832367906")


@pytest.fixture
def read_db() -> FakeFirestoreClient:
    return FakeFirestoreClient()


@pytest.fixture
def target_repo(read_db: FakeFirestoreClient) -> CrawlTargetRepository:
    return CrawlTargetRepository(read_db)


@pytest.fixture
def alert_repo(read_db: FakeFirestoreClient) -> PriceAlertRepository:
    return PriceAlertRepository(read_db)


@pytest.fixture
def crawler_view(read_db: FakeFirestoreClient, target_repo: CrawlTargetRepository) -> CrawlerOperationsView:
    return CrawlerOperationsView(target_repo, read_db)


@pytest.fixture
def price_view(read_db: FakeFirestoreClient, target_repo: CrawlTargetRepository) -> PriceOperationsView:
    return PriceOperationsView(target_repo, read_db)


@pytest.fixture
def alert_view(
    alert_repo: PriceAlertRepository,
    target_repo: CrawlTargetRepository,
    price_view: PriceOperationsView,
) -> AlertOperationsView:
    return AlertOperationsView(alert_repo, target_repo, price_view)


@pytest.fixture
def audit_view(alert_repo: PriceAlertRepository) -> AuditOperationsView:
    return AuditOperationsView(alert_repo)


def _seed_target(repo: CrawlTargetRepository) -> None:
    repo.merge_catalog(
        mall_id="ssg",
        product_url=PRODUCT_URL,
        product_name="GPU",
        category="gpu",
        tags=["zotac"],
        priority=100,
        now=NOW,
    )


def _seed_listing(read_db: FakeFirestoreClient) -> None:
    read_db.collection(c.LISTINGS).document(LISTING_ID).set(
        {
            "product_id": "prod-1",
            "current_price": 1_599_000,
            "crawled_at": NOW,
        }
    )
    read_db.collection(c.LISTINGS).document(LISTING_ID).collection(c.PRICE_HISTORY).document("h1").set(
        {
            "price": 1_599_000,
            "previous_price": 1_649_000,
            "price_change": -50_000,
            "crawled_at": NOW,
        }
    )


def _seed_alert(alert_repo: PriceAlertRepository) -> None:
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_UP,
        threshold=100_000,
        enabled=True,
        now=NOW,
    )


def _count_list_all(target_repo: CrawlTargetRepository) -> dict[str, int]:
    counts = {"n": 0}
    original = target_repo.list_all

    def wrapped(**kwargs: object) -> list:
        counts["n"] += 1
        return original(**kwargs)

    target_repo.list_all = wrapped  # type: ignore[method-assign]
    return counts


def test_command_center_builds_dashboard_once() -> None:
    view = build_command_center_operations_view()
    dashboard_view = view._dashboard
    original_build = dashboard_view.build_dashboard_snapshot
    call_count = {"n": 0}

    def counting_build(**kwargs: object):
        call_count["n"] += 1
        return original_build(**kwargs)

    dashboard_view.build_dashboard_snapshot = counting_build  # type: ignore[method-assign]
    view.build_snapshot(filters=CommandCenterFilter(recent=3), now=NOW)
    assert call_count["n"] == 1


def test_remediation_reuses_investigation_snapshot() -> None:
    investigation_view = InvestigationOperationsView(MagicMock())
    remediation_view = RemediationOperationsView(investigation_view)
    investigation_view.investigate_dashboard = MagicMock()  # type: ignore[method-assign]
    remediation_view.build_remediation_plan(
        investigation=MagicMock(findings=(), summary=MagicMock(total_findings=0), health=MagicMock(value="HEALTHY")),
        now=NOW,
    )
    investigation_view.investigate_dashboard.assert_not_called()


def test_crawler_targets_list_all_deduplicated_in_dashboard(
    crawler_view: CrawlerOperationsView,
    target_repo: CrawlTargetRepository,
) -> None:
    _seed_target(target_repo)
    counts = _count_list_all(target_repo)
    with operations_read_scope():
        crawler_view.summarize(now=NOW)
        crawler_view.list_targets(now=NOW)
        crawler_view.list_recent_failures()
        crawler_view.summarize_by_mall(now=NOW)
    assert counts["n"] == 1


def test_price_listing_and_history_reads_deduplicated_per_target(
    monkeypatch: pytest.MonkeyPatch,
    price_view: PriceOperationsView,
    target_repo: CrawlTargetRepository,
    read_db: FakeFirestoreClient,
) -> None:
    from pricebrain_app.crawler import price_operations_view as price_view_module

    _seed_target(target_repo)
    _seed_listing(read_db)
    listing_gets = {"n": 0}
    history_reads = {"n": 0}
    original_get = price_view_module._get_listing_document_data
    original_history = price_view_module._read_price_history

    def counting_get(*args: object, **kwargs: object):
        listing_gets["n"] += 1
        return original_get(*args, **kwargs)

    def counting_history(*args: object, **kwargs: object):
        history_reads["n"] += 1
        return original_history(*args, **kwargs)

    monkeypatch.setattr(price_view_module, "_get_listing_document_data", counting_get)
    monkeypatch.setattr(price_view_module, "_read_price_history", counting_history)

    with operations_read_scope():
        price_view.get_price_summary(TARGET_ID)
        price_view.get_current_price(TARGET_ID)
    assert listing_gets["n"] == 1
    assert history_reads["n"] == 1


def test_alerts_collection_stream_deduplicated_in_summarize(
    monkeypatch: pytest.MonkeyPatch,
    alert_view: AlertOperationsView,
    target_repo: CrawlTargetRepository,
    alert_repo: PriceAlertRepository,
    read_db: FakeFirestoreClient,
) -> None:
    from pricebrain_app.tests.fake_firestore import FakeCollectionReference

    _seed_target(target_repo)
    _seed_listing(read_db)
    _seed_alert(alert_repo)
    stream_counts = {"n": 0}
    original_stream = FakeCollectionReference.stream

    def counting_stream(self):
        if self._collection_path == PRICE_ALERTS_COLLECTION:
            stream_counts["n"] += 1
        return original_stream(self)

    monkeypatch.setattr(FakeCollectionReference, "stream", counting_stream)

    with operations_read_scope():
        alert_view.summarize_alerts(now=NOW)
    assert stream_counts["n"] == 1
