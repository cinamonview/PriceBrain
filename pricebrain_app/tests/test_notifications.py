"""Notification adapter, dispatcher, and alert integration tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.crawler.notification_adapter import (
    ConsoleNotificationAdapter,
    FakeNotificationAdapter,
    FailingNotificationAdapter,
)
from pricebrain_app.crawler.notification_builder import build_notification_event
from pricebrain_app.crawler.notification_dispatcher import NotificationDispatcher
from pricebrain_app.crawler.notification_models import (
    NotificationChannel,
    NotificationEvent,
    NotificationSendStatus,
)
from pricebrain_app.crawler.price_alert_models import (
    AlertEvaluationOutcome,
    AlertEvaluationResult,
    PriceAlert,
    PriceAlertType,
)
from pricebrain_app.crawler.price_alert_repository import PriceAlertRepository
from pricebrain_app.crawler.price_alert_service import PriceAlertService, evaluate_alert
from pricebrain_app.crawler.price_ops_models import PriceChangeClassification, PriceSnapshot
from pricebrain_app.crawler.price_operations_view import PriceOperationsView
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.listing_repository import build_listing_document_id
from pricebrain_app.scripts import test_notifications
from pricebrain_app.tests.conftest import TEST_INGEST_API_KEY
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
TARGET_ID = "ssg_1000832367906"
PRODUCT_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
LISTING_ID = build_listing_document_id("ssg", "1000832367906")


@pytest.fixture
def notify_db() -> FakeFirestoreClient:
    return FakeFirestoreClient()


@pytest.fixture
def notify_repo(notify_db: FakeFirestoreClient) -> PriceAlertRepository:
    return PriceAlertRepository(notify_db)


@pytest.fixture
def target_repo(notify_db: FakeFirestoreClient) -> CrawlTargetRepository:
    return CrawlTargetRepository(notify_db)


@pytest.fixture
def price_view(notify_db: FakeFirestoreClient, target_repo: CrawlTargetRepository) -> PriceOperationsView:
    return PriceOperationsView(target_repo, notify_db)


def _event(**overrides: object) -> NotificationEvent:
    payload = {
        "notification_id": "notification-1",
        "alert_id": "alert-1",
        "target_id": TARGET_ID,
        "mall_id": "ssg",
        "alert_type": "PRICE_BELOW",
        "channel": NotificationChannel.FAKE,
        "title": "Test",
        "message": "Test message",
        "current_price": 1_490_000,
        "previous_price": 1_599_000,
        "price_change": -109_000,
        "price_change_percent": -6.82,
        "product_name": "Test GPU",
        "brand": "zotac",
        "created_at": NOW,
    }
    payload.update(overrides)
    return NotificationEvent(**payload)


def _snapshot(**overrides: object) -> PriceSnapshot:
    payload = {
        "target_id": TARGET_ID,
        "product_id": None,
        "listing_id": LISTING_ID,
        "mall_id": "ssg",
        "external_product_id": "1000832367906",
        "product_url": PRODUCT_URL,
        "product_name": "ZOTAC RTX 5080",
        "price": 1_490_000,
        "previous_price": 1_599_000,
        "price_change": -109_000,
        "price_change_percent": -6.82,
        "observed_at": NOW,
        "classification": PriceChangeClassification.PRICE_DOWN,
    }
    payload.update(overrides)
    return PriceSnapshot(**payload)


def _alert(alert_type: PriceAlertType, **overrides: object) -> PriceAlert:
    payload = {
        "alert_id": "alert-1",
        "target_id": TARGET_ID,
        "mall_id": "ssg",
        "alert_type": alert_type,
        "threshold": 1_500_000,
        "product_name": "ZOTAC RTX 5080",
        "brand": "zotac",
    }
    payload.update(overrides)
    return PriceAlert(**payload)


def _result(alert: PriceAlert, **overrides: object) -> AlertEvaluationResult:
    payload = {
        "alert_id": alert.alert_id,
        "target_id": alert.target_id,
        "alert_type": alert.alert_type,
        "outcome": AlertEvaluationOutcome.TRIGGERED,
        "current_price": 1_490_000,
        "previous_price": 1_599_000,
        "threshold": alert.threshold,
        "message": "triggered",
        "observed_at": NOW,
    }
    payload.update(overrides)
    return AlertEvaluationResult(**payload)


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


def test_a_console_adapter_send() -> None:
    adapter = ConsoleNotificationAdapter()
    result = adapter.send(_event(channel=NotificationChannel.CONSOLE))
    assert result.status is NotificationSendStatus.SENT
    assert result.channel is NotificationChannel.CONSOLE


def test_b_fake_adapter_send() -> None:
    adapter = FakeNotificationAdapter()
    result = adapter.send(_event())
    assert result.status is NotificationSendStatus.SENT
    assert len(adapter.sent_events) == 1


def test_c_dispatcher_selects_adapter() -> None:
    fake = FakeNotificationAdapter()
    dispatcher = NotificationDispatcher({NotificationChannel.FAKE: fake})
    result = dispatcher.dispatch(_event())
    assert result.status is NotificationSendStatus.SENT
    assert len(fake.sent_events) == 1


def test_d_unsupported_channel_returns_unsupported() -> None:
    dispatcher = NotificationDispatcher()
    result = dispatcher.dispatch(_event(channel=NotificationChannel.EMAIL))
    assert result.status is NotificationSendStatus.UNSUPPORTED


def test_e_adapter_exception_returns_failed() -> None:
    dispatcher = NotificationDispatcher({NotificationChannel.FAKE: FailingNotificationAdapter()})
    result = dispatcher.dispatch(_event())
    assert result.status is NotificationSendStatus.FAILED


def test_f_notification_failure_does_not_fail_alert_evaluation(
    notify_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
    target_repo: CrawlTargetRepository,
    notify_db: FakeFirestoreClient,
) -> None:
    _seed_target(target_repo)
    _seed_listing(notify_db, current=1_490_000, previous=1_599_000)
    notify_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    service = PriceAlertService(
        notify_repo,
        price_view,
        notification_dispatcher=NotificationDispatcher({NotificationChannel.FAKE: FailingNotificationAdapter()}),
        default_channel=NotificationChannel.FAKE,
        notifications_enabled_override=True,
    )
    results, summary, notifications = service.check_enabled_alerts(now=NOW)
    assert summary.triggered == 1
    assert results[0].outcome is AlertEvaluationOutcome.TRIGGERED
    assert notifications[0].status is NotificationSendStatus.FAILED


@pytest.mark.parametrize(
    "alert_type,threshold,current,previous",
    [
        (PriceAlertType.PRICE_BELOW, 1_500_000, 1_490_000, 1_599_000),
        (PriceAlertType.PRICE_DROP_PERCENT, 5, 1_520_000, 1_600_000),
        (PriceAlertType.PRICE_DROP_AMOUNT, 50_000, 1_550_000, 1_600_000),
        (PriceAlertType.PRICE_UP, 0, 1_600_000, 1_550_000),
        (PriceAlertType.PRICE_CHANGED, 0, 1_600_000, 1_550_000),
    ],
    ids=[
        "price-below",
        "price-drop-percent",
        "price-drop-amount",
        "price-up",
        "price-changed",
    ],
)
def test_g_to_k_notification_event_created_for_triggered_alerts(
    alert_type: PriceAlertType,
    threshold: float,
    current: int,
    previous: int,
) -> None:
    alert = _alert(alert_type, threshold=threshold)
    snapshot = _snapshot(price=current, previous_price=previous)
    evaluation = evaluate_alert(alert, snapshot, now=NOW)
    assert evaluation.outcome is AlertEvaluationOutcome.TRIGGERED
    event = build_notification_event(
        alert,
        evaluation,
        snapshot,
        channel=NotificationChannel.FAKE,
        now=NOW,
    )
    assert event is not None
    assert event.alert_type == alert_type.value
    assert event.current_price == current


def test_l_no_history_does_not_create_notification_event() -> None:
    alert = _alert(PriceAlertType.PRICE_BELOW)
    snapshot = _snapshot(
        price=None,
        previous_price=None,
        classification=PriceChangeClassification.NO_HISTORY,
    )
    evaluation = evaluate_alert(alert, snapshot, now=NOW)
    assert evaluation.outcome is AlertEvaluationOutcome.INVALID
    assert build_notification_event(alert, evaluation, snapshot, channel=NotificationChannel.FAKE) is None


def test_m_invalid_price_does_not_create_notification_event() -> None:
    alert = _alert(PriceAlertType.PRICE_BELOW)
    snapshot = _snapshot(price=0, classification=PriceChangeClassification.INVALID_PRICE)
    evaluation = evaluate_alert(alert, snapshot, now=NOW)
    assert evaluation.outcome is AlertEvaluationOutcome.INVALID
    assert build_notification_event(alert, evaluation, snapshot, channel=NotificationChannel.FAKE) is None


def test_n_duplicate_policy_still_skips_second_trigger(
    notify_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
    target_repo: CrawlTargetRepository,
    notify_db: FakeFirestoreClient,
) -> None:
    _seed_target(target_repo)
    _seed_listing(notify_db, current=1_490_000, previous=1_599_000)
    notify_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    fake = FakeNotificationAdapter()
    service = PriceAlertService(
        notify_repo,
        price_view,
        notification_dispatcher=NotificationDispatcher({NotificationChannel.FAKE: fake}),
        default_channel=NotificationChannel.FAKE,
        notifications_enabled_override=True,
    )
    first_results, first_summary, first_notifications = service.check_enabled_alerts(now=NOW)
    second_results, second_summary, second_notifications = service.check_enabled_alerts(now=NOW)

    assert first_summary.triggered == 1
    assert len(first_notifications) == 1
    assert second_summary.skipped == 1
    assert second_results[0].outcome is AlertEvaluationOutcome.SKIPPED
    assert second_notifications == []


def test_o_security_json_has_no_api_key(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()
    test_notifications.main(["--json"])
    text = capsys.readouterr().out
    assert TEST_INGEST_API_KEY not in text
    assert "Authorization" not in text


def test_notification_enabled_dispatches_on_trigger(
    notify_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
    target_repo: CrawlTargetRepository,
    notify_db: FakeFirestoreClient,
) -> None:
    _seed_target(target_repo)
    _seed_listing(notify_db, current=1_490_000, previous=1_599_000)
    notify_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    fake = FakeNotificationAdapter()
    service = PriceAlertService(
        notify_repo,
        price_view,
        notification_dispatcher=NotificationDispatcher({NotificationChannel.FAKE: fake}),
        default_channel=NotificationChannel.FAKE,
        notifications_enabled_override=True,
    )
    _, summary, notifications = service.check_enabled_alerts(now=NOW)
    assert summary.triggered == 1
    assert notifications[0].status is NotificationSendStatus.SENT
    assert len(fake.sent_events) == 1


def test_test_notifications_cli_json(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = test_notifications.main(["--json"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["result"]["status"] == "SENT"
