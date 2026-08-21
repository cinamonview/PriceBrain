"""Price alert evaluation, repository, and CLI tests — FakeFirestore only."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.crawler.price_alert_models import (
    AlertEvaluationOutcome,
    PriceAlert,
    PriceAlertType,
)
from pricebrain_app.crawler.price_alert_repository import PriceAlertRepository
from pricebrain_app.crawler.price_alert_service import PriceAlertService, evaluate_alert
from pricebrain_app.crawler.price_calculations import build_price_snapshot, build_price_summary
from pricebrain_app.crawler.price_ops_models import PriceChangeClassification, PriceSnapshot
from pricebrain_app.crawler.price_operations_view import PriceOperationsView
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.targets import CrawlTarget
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.listing_repository import build_listing_document_id
from pricebrain_app.scripts import check_price_alerts, create_price_alert, disable_price_alert, list_price_alerts
from pricebrain_app.tests.conftest import TEST_INGEST_API_KEY
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
TARGET_ID = "ssg_1000832367906"
PRODUCT_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
LISTING_ID = build_listing_document_id("ssg", "1000832367906")


@pytest.fixture
def alert_db() -> FakeFirestoreClient:
    return FakeFirestoreClient()


@pytest.fixture
def alert_repo(alert_db: FakeFirestoreClient) -> PriceAlertRepository:
    return PriceAlertRepository(alert_db)


@pytest.fixture
def target_repo(alert_db: FakeFirestoreClient) -> CrawlTargetRepository:
    return CrawlTargetRepository(alert_db)


@pytest.fixture
def price_view(alert_db: FakeFirestoreClient, target_repo: CrawlTargetRepository) -> PriceOperationsView:
    return PriceOperationsView(target_repo, alert_db)


@pytest.fixture
def alert_service(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
) -> PriceAlertService:
    return PriceAlertService(alert_repo, price_view)


def _snapshot(**overrides: object) -> PriceSnapshot:
    payload = {
        "target_id": TARGET_ID,
        "product_id": None,
        "listing_id": LISTING_ID,
        "mall_id": "ssg",
        "external_product_id": "1000832367906",
        "product_url": PRODUCT_URL,
        "product_name": "ZOTAC RTX 5080",
        "price": 1_549_000,
        "previous_price": 1_599_000,
        "price_change": -50_000,
        "price_change_percent": -3.13,
        "observed_at": NOW,
        "classification": PriceChangeClassification.PRICE_DOWN,
    }
    payload.update(overrides)
    return PriceSnapshot(**payload)


def _alert(**overrides: object) -> PriceAlert:
    payload = {
        "alert_id": "alert-1",
        "target_id": TARGET_ID,
        "mall_id": "ssg",
        "alert_type": PriceAlertType.PRICE_BELOW,
        "threshold": 1_500_000,
    }
    payload.update(overrides)
    return PriceAlert(**payload)


def _seed_target(repo: CrawlTargetRepository) -> None:
    repo.merge_catalog(
        mall_id="ssg",
        product_url=PRODUCT_URL,
        product_name="ZOTAC RTX 5080",
        category="gpu",
        tags=["zotac"],
        priority=100,
        now=NOW,
    )


def _seed_listing(db: FakeFirestoreClient, *, current: int, previous: int | None = None) -> None:
    db.collection(c.LISTINGS).document(LISTING_ID).set(
        {
            "normalized_product_name": "ZOTAC RTX 5080",
            "current_price": current,
            "crawled_at": NOW,
        }
    )
    db.collection(c.LISTINGS).document(LISTING_ID).collection(c.PRICE_HISTORY).document("1").set(
        {
            "price": current,
            "previous_price": previous,
            "price_change": (current - previous) if previous is not None else None,
            "crawled_at": NOW,
        }
    )


def test_price_below_trigger() -> None:
    result = evaluate_alert(_alert(threshold=1_500_000), _snapshot(price=1_490_000))
    assert result.outcome is AlertEvaluationOutcome.TRIGGERED


def test_price_below_no_trigger() -> None:
    result = evaluate_alert(_alert(threshold=1_500_000), _snapshot(price=1_510_000))
    assert result.outcome is AlertEvaluationOutcome.NOT_TRIGGERED


def test_price_below_threshold_exact_match() -> None:
    result = evaluate_alert(_alert(threshold=1_500_000), _snapshot(price=1_500_000))
    assert result.outcome is AlertEvaluationOutcome.TRIGGERED


def test_price_drop_percent_trigger() -> None:
    result = evaluate_alert(
        _alert(alert_type=PriceAlertType.PRICE_DROP_PERCENT, threshold=20),
        _snapshot(price=1_600_000, previous_price=2_000_000),
    )
    assert result.outcome is AlertEvaluationOutcome.TRIGGERED


def test_price_drop_percent_no_trigger() -> None:
    result = evaluate_alert(
        _alert(alert_type=PriceAlertType.PRICE_DROP_PERCENT, threshold=20),
        _snapshot(price=1_900_000, previous_price=2_000_000),
    )
    assert result.outcome is AlertEvaluationOutcome.NOT_TRIGGERED


def test_price_drop_amount_trigger() -> None:
    result = evaluate_alert(
        _alert(alert_type=PriceAlertType.PRICE_DROP_AMOUNT, threshold=50_000),
        _snapshot(price=1_950_000, previous_price=2_000_000),
    )
    assert result.outcome is AlertEvaluationOutcome.TRIGGERED


def test_price_drop_amount_exact_threshold() -> None:
    result = evaluate_alert(
        _alert(alert_type=PriceAlertType.PRICE_DROP_AMOUNT, threshold=50_000),
        _snapshot(price=1_950_000, previous_price=2_000_000),
    )
    assert result.outcome is AlertEvaluationOutcome.TRIGGERED


def test_price_up_trigger() -> None:
    result = evaluate_alert(
        _alert(alert_type=PriceAlertType.PRICE_UP, threshold=0),
        _snapshot(price=1_599_000, previous_price=1_549_000, classification=PriceChangeClassification.PRICE_UP),
    )
    assert result.outcome is AlertEvaluationOutcome.TRIGGERED


def test_price_changed_trigger() -> None:
    result = evaluate_alert(
        _alert(alert_type=PriceAlertType.PRICE_CHANGED, threshold=0),
        _snapshot(price=1_549_000, previous_price=1_599_000),
    )
    assert result.outcome is AlertEvaluationOutcome.TRIGGERED


def test_invalid_zero_price() -> None:
    result = evaluate_alert(_alert(), _snapshot(price=0, classification=PriceChangeClassification.INVALID_PRICE))
    assert result.outcome is AlertEvaluationOutcome.INVALID


def test_invalid_negative_price() -> None:
    result = evaluate_alert(_alert(), _snapshot(price=-100, classification=PriceChangeClassification.INVALID_PRICE))
    assert result.outcome is AlertEvaluationOutcome.INVALID


def test_no_current_price_no_history() -> None:
    result = evaluate_alert(
        _alert(),
        _snapshot(price=None, previous_price=None, classification=PriceChangeClassification.NO_HISTORY),
    )
    assert result.outcome is AlertEvaluationOutcome.INVALID


def test_drop_percent_without_previous_price() -> None:
    result = evaluate_alert(
        _alert(alert_type=PriceAlertType.PRICE_DROP_PERCENT, threshold=10),
        _snapshot(price=1_600_000, previous_price=None, classification=PriceChangeClassification.NO_HISTORY),
    )
    assert result.outcome is AlertEvaluationOutcome.INVALID


def test_drop_percent_with_zero_previous_price() -> None:
    result = evaluate_alert(
        _alert(alert_type=PriceAlertType.PRICE_DROP_PERCENT, threshold=10),
        _snapshot(price=1_600_000, previous_price=0),
    )
    assert result.outcome is AlertEvaluationOutcome.NOT_TRIGGERED


def test_duplicate_trigger_same_price() -> None:
    alert = _alert(last_triggered_at=NOW, last_observed_price=1_490_000)
    result = evaluate_alert(alert, _snapshot(price=1_490_000))
    assert result.outcome is AlertEvaluationOutcome.SKIPPED


def test_retrigger_after_price_change(
    alert_repo: PriceAlertRepository,
    alert_service: PriceAlertService,
    target_repo: CrawlTargetRepository,
    alert_db: FakeFirestoreClient,
) -> None:
    _seed_target(target_repo)
    _seed_listing(alert_db, current=1_490_000, previous=1_599_000)
    alert = alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )

    first, _ = alert_service.check_enabled_alerts(now=NOW)
    assert first[0].outcome is AlertEvaluationOutcome.TRIGGERED

    second, summary = alert_service.check_enabled_alerts(now=NOW)
    assert second[0].outcome is AlertEvaluationOutcome.SKIPPED
    assert summary.skipped == 1

    alert_db.collection(c.LISTINGS).document(LISTING_ID).collection(c.PRICE_HISTORY).document("2").set(
        {
            "price": 1_600_000,
            "previous_price": 1_490_000,
            "price_change": 110_000,
            "crawled_at": NOW.replace(hour=13),
        }
    )
    alert_db.collection(c.LISTINGS).document(LISTING_ID).set({"current_price": 1_600_000}, merge=True)

    intermediate, _ = alert_service.check_enabled_alerts(now=NOW.replace(hour=13))
    assert intermediate[0].outcome is AlertEvaluationOutcome.NOT_TRIGGERED

    alert_db.collection(c.LISTINGS).document(LISTING_ID).set({"current_price": 1_490_000}, merge=True)
    alert_db.collection(c.LISTINGS).document(LISTING_ID).collection(c.PRICE_HISTORY).document("3").set(
        {
            "price": 1_490_000,
            "previous_price": 1_600_000,
            "price_change": -110_000,
            "crawled_at": NOW.replace(hour=14),
        }
    )

    third, summary = alert_service.check_enabled_alerts(now=NOW.replace(hour=14))
    assert third[0].outcome is AlertEvaluationOutcome.TRIGGERED
    assert summary.triggered == 1


def test_no_history_snapshot_invalid(
    alert_service: PriceAlertService,
    alert_repo: PriceAlertRepository,
    target_repo: CrawlTargetRepository,
) -> None:
    _seed_target(target_repo)
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    target_repo.update_after_crawl(
        TARGET_ID,
        result=__import__("pricebrain_app.crawler.results", fromlist=["CrawlerResult", "CrawlerStatus"]).CrawlerResult(
            status=__import__("pricebrain_app.crawler.results", fromlist=["CrawlerStatus"]).CrawlerStatus.HTTP_ERROR,
            mall_id="ssg",
            product_url=PRODUCT_URL,
            message="SSG_ACCESS_DENIED",
        ),
        next_crawl_at=NOW,
        crawled_at=NOW,
    )
    results, summary = alert_service.check_enabled_alerts(now=NOW)
    assert results[0].outcome is AlertEvaluationOutcome.INVALID
    assert summary.invalid == 1


def test_failure_isolation_between_targets(
    alert_service: PriceAlertService,
    alert_repo: PriceAlertRepository,
    target_repo: CrawlTargetRepository,
    alert_db: FakeFirestoreClient,
) -> None:
    _seed_target(target_repo)
    target_repo.merge_catalog(
        mall_id="ssg",
        product_url="https://www.ssg.com/item/itemView.ssg?itemId=2222222222222",
        product_name="Other GPU",
        category="gpu",
        now=NOW,
    )
    _seed_listing(alert_db, current=1_490_000, previous=1_599_000)
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    alert_repo.create(
        target_id="ssg_2222222222222",
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )

    results, summary = alert_service.check_enabled_alerts(now=NOW)
    assert summary.total == 2
    assert summary.triggered == 1
    assert summary.invalid == 1


def test_repository_create_get_list(alert_repo: PriceAlertRepository) -> None:
    created = alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    loaded = alert_repo.get(created.alert_id)
    assert loaded is not None
    assert loaded.target_id == TARGET_ID
    assert len(alert_repo.list_all()) == 1
    assert len(alert_repo.list_enabled()) == 1


def test_repository_update_disable_and_mark_triggered(alert_repo: PriceAlertRepository) -> None:
    created = alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    disabled = alert_repo.set_enabled(created.alert_id, enabled=False)
    assert disabled.enabled is False
    assert alert_repo.list_enabled() == []

    enabled = alert_repo.set_enabled(created.alert_id, enabled=True)
    triggered = alert_repo.mark_triggered(enabled.alert_id, observed_price=1_490_000, triggered_at=NOW)
    assert triggered.last_observed_price == 1_490_000
    assert triggered.last_triggered_at == NOW


def test_repository_delete_disables_alert(alert_repo: PriceAlertRepository) -> None:
    created = alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    assert alert_repo.delete(created.alert_id) is True
    saved = alert_repo.get(created.alert_id)
    assert saved is not None
    assert saved.enabled is False


def test_create_price_alert_cli(
    alert_repo: PriceAlertRepository,
    target_repo: CrawlTargetRepository,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _seed_target(target_repo)
    monkeypatch.setattr(create_price_alert, "build_price_alert_repository", lambda: alert_repo)
    monkeypatch.setattr(create_price_alert, "build_target_repository", lambda: target_repo)

    exit_code = create_price_alert.main(
        ["--target-id", TARGET_ID, "--type", "price-below", "--threshold", "1500000", "--json"]
    )
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["alert_type"] == "PRICE_BELOW"


def test_list_and_disable_alert_cli(
    alert_repo: PriceAlertRepository,
    target_repo: CrawlTargetRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_target(target_repo)
    alert = alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    monkeypatch.setattr(list_price_alerts, "build_price_alert_repository", lambda: alert_repo)
    monkeypatch.setattr(disable_price_alert, "build_price_alert_repository", lambda: alert_repo)

    assert list_price_alerts.main(["--json"]) == 0
    assert disable_price_alert.main(["--alert-id", alert.alert_id]) == 0


def test_check_price_alerts_cli(
    alert_service: PriceAlertService,
    alert_repo: PriceAlertRepository,
    target_repo: CrawlTargetRepository,
    alert_db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_target(target_repo)
    _seed_listing(alert_db, current=1_490_000, previous=1_599_000)
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    monkeypatch.setattr(check_price_alerts, "build_price_alert_service", lambda: alert_service)
    assert check_price_alerts.main(["--json"]) == 0


def test_security_json_has_no_api_key(
    alert_repo: PriceAlertRepository,
    target_repo: CrawlTargetRepository,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _seed_target(target_repo)
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()
    monkeypatch.setattr(list_price_alerts, "build_price_alert_repository", lambda: alert_repo)

    list_price_alerts.main(["--json"])
    text = capsys.readouterr().out
    assert TEST_INGEST_API_KEY not in text
    assert "Authorization" not in text


def test_build_price_summary_to_snapshot_for_alerts() -> None:
    target = CrawlTarget(
        target_id=TARGET_ID,
        mall_id="ssg",
        product_url=PRODUCT_URL,
        product_name="ZOTAC RTX 5080",
    )
    summary = build_price_summary(
        target,
        listing_id=LISTING_ID,
        listing_data={"current_price": 1_549_000},
        history_entries=[
            {
                "price": 1_549_000,
                "previous_price": 1_599_000,
                "price_change": -50_000,
                "crawled_at": NOW.isoformat(),
            }
        ],
    )
    snapshot = build_price_snapshot(summary)
    result = evaluate_alert(_alert(threshold=1_600_000), snapshot)
    assert result.outcome is AlertEvaluationOutcome.TRIGGERED
