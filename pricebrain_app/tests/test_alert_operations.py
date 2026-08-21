"""Alert, notification, and runner operations read-only tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from pricebrain_app.config.settings import clear_settings_cache, get_settings
from pricebrain_app.crawler.alert_operations_models import AlertListFilter
from pricebrain_app.crawler.alert_operations_view import AlertOperationsView
from pricebrain_app.crawler.alert_ops_health_store import (
    AlertOpsHealthStore,
    RecordedNotificationEvent,
    get_alert_ops_health_store,
    reset_alert_ops_health_store,
)
from pricebrain_app.crawler.notification_adapter import FakeNotificationAdapter, FailingNotificationAdapter
from pricebrain_app.crawler.notification_dispatcher import NotificationDispatcher
from pricebrain_app.crawler.notification_models import NotificationChannel, NotificationSendStatus
from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction
from pricebrain_app.crawler.price_alert_models import PRICE_ALERTS_COLLECTION, PriceAlertType
from pricebrain_app.crawler.price_alert_repository import PriceAlertRepository
from pricebrain_app.crawler.price_alert_runner import PriceAlertRunner, PriceAlertRunnerCycleResult
from pricebrain_app.crawler.price_alert_service import PriceAlertService
from pricebrain_app.crawler.price_operations_view import PriceOperationsView
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.listing_repository import build_listing_document_id
from pricebrain_app.scripts import (
    list_price_alerts,
    show_notification_status,
    show_price_alert,
    show_price_alert_runner,
    show_price_alert_status,
)
from pricebrain_app.tests.conftest import TEST_INGEST_API_KEY
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
TARGET_ID = "ssg_1000832367906"
PRODUCT_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
LISTING_ID = build_listing_document_id("ssg", "1000832367906")


@pytest.fixture(autouse=True)
def _reset_health_store() -> None:
    reset_alert_ops_health_store()


@pytest.fixture
def ops_db() -> FakeFirestoreClient:
    return FakeFirestoreClient()


@pytest.fixture
def alert_repo(ops_db: FakeFirestoreClient) -> PriceAlertRepository:
    return PriceAlertRepository(ops_db)


@pytest.fixture
def target_repo(ops_db: FakeFirestoreClient) -> CrawlTargetRepository:
    return CrawlTargetRepository(ops_db)


@pytest.fixture
def price_view(ops_db: FakeFirestoreClient, target_repo: CrawlTargetRepository) -> PriceOperationsView:
    return PriceOperationsView(target_repo, ops_db)


@pytest.fixture
def health_store() -> AlertOpsHealthStore:
    return get_alert_ops_health_store()


@pytest.fixture
def ops_view(
    alert_repo: PriceAlertRepository,
    target_repo: CrawlTargetRepository,
    price_view: PriceOperationsView,
    health_store: AlertOpsHealthStore,
) -> AlertOperationsView:
    return AlertOperationsView(alert_repo, target_repo, price_view, health_store=health_store)


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


def _service(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
    *,
    failing: bool = False,
) -> PriceAlertService:
    adapter = FailingNotificationAdapter() if failing else FakeNotificationAdapter()
    return PriceAlertService(
        alert_repo,
        price_view,
        notification_dispatcher=NotificationDispatcher({NotificationChannel.FAKE: adapter}),
        default_channel=NotificationChannel.FAKE,
        notifications_enabled_override=True,
    )


def test_a_alert_summary_zero_alerts(ops_view: AlertOperationsView) -> None:
    summary = ops_view.summarize_alerts()
    assert summary.total == 0
    assert summary.enabled == 0
    assert summary.disabled == 0


def test_b_enabled_disabled_counts(
    alert_repo: PriceAlertRepository,
    ops_view: AlertOperationsView,
) -> None:
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        enabled=True,
        now=NOW,
    )
    disabled = alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_UP,
        threshold=1,
        enabled=False,
        now=NOW,
    )
    assert disabled.enabled is False
    summary = ops_view.summarize_alerts()
    assert summary.total == 2
    assert summary.enabled == 1
    assert summary.disabled == 1


def test_c_alert_type_aggregation(
    alert_repo: PriceAlertRepository,
    ops_view: AlertOperationsView,
) -> None:
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_400_000,
        now=NOW,
    )
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_UP,
        threshold=1,
        now=NOW,
    )
    summary = ops_view.summarize_alerts()
    assert dict(summary.by_type) == {"PRICE_BELOW": 2, "PRICE_UP": 1}


def test_d_mall_aggregation(
    alert_repo: PriceAlertRepository,
    ops_view: AlertOperationsView,
) -> None:
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    alert_repo.create(
        target_id="other_target",
        mall_id="coupang",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    summary = ops_view.summarize_alerts()
    assert dict(summary.by_mall) == {"coupang": 1, "ssg": 1}


def test_e_alert_snapshot_detail(
    alert_repo: PriceAlertRepository,
    target_repo: CrawlTargetRepository,
    ops_db: FakeFirestoreClient,
    ops_view: AlertOperationsView,
) -> None:
    _seed_target(target_repo)
    _seed_listing(ops_db, current=1_490_000, previous=1_599_000)
    alert = alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    snapshot = ops_view.get_alert_snapshot(alert.alert_id)
    assert snapshot is not None
    assert snapshot.current_price == 1_490_000
    assert snapshot.previous_price == 1_599_000
    assert snapshot.classification == "PRICE_DOWN"
    assert snapshot.category == "gpu"


def test_f_malformed_alert_isolation(
    ops_db: FakeFirestoreClient,
    alert_repo: PriceAlertRepository,
    ops_view: AlertOperationsView,
) -> None:
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    ops_db.collection(PRICE_ALERTS_COLLECTION).document("bad-alert").set({"threshold": "not-a-number"})
    summary = ops_view.summarize_alerts()
    assert summary.total == 1
    assert summary.read_errors >= 1


def test_g_notification_sent_count(health_store: AlertOpsHealthStore, ops_view: AlertOperationsView) -> None:
    health_store._notifications.appendleft(
        RecordedNotificationEvent(
            notification_id="n1",
            alert_id="a1",
            target_id=TARGET_ID,
            channel=NotificationChannel.FAKE.value,
            status=NotificationSendStatus.SENT.value,
            message="ok",
            recorded_at=NOW,
        )
    )
    summary = ops_view.summarize_notifications()
    assert summary.notification_sent == 1
    assert summary.notification_failed == 0


def test_h_notification_failed_count(health_store: AlertOpsHealthStore, ops_view: AlertOperationsView) -> None:
    health_store._notifications.appendleft(
        RecordedNotificationEvent(
            notification_id="n1",
            alert_id="a1",
            target_id=TARGET_ID,
            channel=NotificationChannel.FAKE.value,
            status=NotificationSendStatus.FAILED.value,
            message="failed",
            recorded_at=NOW,
        )
    )
    summary = ops_view.summarize_notifications()
    assert summary.notification_failed == 1


def test_i_notification_channel_aggregation(
    health_store: AlertOpsHealthStore,
    ops_view: AlertOperationsView,
) -> None:
    for channel in (NotificationChannel.FAKE.value, NotificationChannel.CONSOLE.value):
        health_store._notifications.appendleft(
            RecordedNotificationEvent(
                notification_id=f"n-{channel}",
                alert_id="a1",
                target_id=TARGET_ID,
                channel=channel,
                status=NotificationSendStatus.SENT.value,
                message="ok",
                recorded_at=NOW,
            )
        )
    summary = ops_view.summarize_notifications()
    assert dict(summary.by_channel) == {NotificationChannel.CONSOLE.value: 1, NotificationChannel.FAKE.value: 1}


def test_j_recent_notification_events(health_store: AlertOpsHealthStore, ops_view: AlertOperationsView) -> None:
    health_store._notifications.appendleft(
        RecordedNotificationEvent(
            notification_id="n1",
            alert_id="a1",
            target_id=TARGET_ID,
            channel=NotificationChannel.FAKE.value,
            status=NotificationSendStatus.SENT.value,
            message="ok",
            recorded_at=NOW,
        )
    )
    summary = ops_view.summarize_notifications(recent_limit=5)
    assert len(summary.recent_events) == 1
    assert summary.recent_events[0]["alert_id"] == "a1"


def test_k_malformed_notification_isolation_does_not_crash(ops_view: AlertOperationsView) -> None:
    summary = ops_view.summarize_notifications()
    assert summary.total_evaluated == 0


def test_l_last_runner_cycle(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
    target_repo: CrawlTargetRepository,
    ops_db: FakeFirestoreClient,
    ops_view: AlertOperationsView,
) -> None:
    _seed_target(target_repo)
    _seed_listing(ops_db, current=1_490_000, previous=1_599_000)
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    PriceAlertRunner(_service(alert_repo, price_view)).run_once(now=NOW)
    health = ops_view.get_runner_health()
    assert health.last_cycle_started_at == NOW
    assert health.triggered == 1


def test_m_runner_duration(ops_view: AlertOperationsView, health_store: AlertOpsHealthStore) -> None:
    started = NOW
    finished = NOW + timedelta(seconds=12)
    health_store.record_cycle(
        PriceAlertRunnerCycleResult(
            cycle_started_at=started,
            cycle_finished_at=finished,
            total_alerts=1,
            evaluated=1,
            triggered=0,
            skipped=0,
            invalid=0,
            not_triggered=1,
            notification_sent=0,
            notification_failed=0,
        )
    )
    health = ops_view.get_runner_health()
    assert health.duration_seconds == pytest.approx(12.0)


def test_n_successful_and_failed_cycles(health_store: AlertOpsHealthStore, ops_view: AlertOperationsView) -> None:
    success_at = NOW
    failed_at = NOW + timedelta(minutes=1)
    health_store.record_cycle(
        PriceAlertRunnerCycleResult(
            cycle_started_at=success_at,
            cycle_finished_at=success_at,
            total_alerts=1,
            evaluated=1,
            triggered=0,
            skipped=0,
            invalid=0,
            not_triggered=1,
            notification_sent=0,
            notification_failed=0,
        )
    )
    health_store.record_cycle(
        PriceAlertRunnerCycleResult(
            cycle_started_at=failed_at,
            cycle_finished_at=failed_at,
            total_alerts=1,
            evaluated=1,
            triggered=1,
            skipped=0,
            invalid=0,
            not_triggered=0,
            notification_sent=0,
            notification_failed=1,
            errors=("notification failed",),
        )
    )
    health = ops_view.get_runner_health()
    assert health.last_failed_cycle_at == failed_at
    assert health.last_successful_cycle_at == success_at


def test_o_runner_health_without_cycles(ops_view: AlertOperationsView) -> None:
    health = ops_view.get_runner_health()
    assert health.last_cycle_started_at is None
    assert health.duration_seconds is None
    assert health.total_alerts == 0


def test_p_operations_view_does_not_write_firestore(
    alert_repo: PriceAlertRepository,
    ops_db: FakeFirestoreClient,
    ops_view: AlertOperationsView,
) -> None:
    writes_before = len(ops_db._data)
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    writes_after_seed = len(ops_db._data)
    ops_view.summarize_alerts()
    ops_view.list_alert_snapshots()
    ops_view.summarize_notifications()
    ops_view.get_runner_health()
    assert len(ops_db._data) == writes_after_seed
    assert writes_after_seed >= writes_before


def test_q_operations_view_does_not_mark_triggered(
    alert_repo: PriceAlertRepository,
    ops_view: AlertOperationsView,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    mark_triggered = MagicMock(side_effect=alert_repo.mark_triggered)
    monkeypatch.setattr(alert_repo, "mark_triggered", mark_triggered)
    ops_view.summarize_alerts()
    ops_view.list_alert_snapshots()
    mark_triggered.assert_not_called()


def test_r_operations_view_does_not_dispatch_notifications(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
    ops_view: AlertOperationsView,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatcher = MagicMock()
    service = PriceAlertService(
        alert_repo,
        price_view,
        notification_dispatcher=dispatcher,
        default_channel=NotificationChannel.FAKE,
        notifications_enabled_override=True,
    )
    assert service is not None
    ops_view.summarize_notifications()
    dispatcher.dispatch.assert_not_called()


def test_s_operations_view_does_not_call_http(
    ops_view: AlertOperationsView,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http_mock = MagicMock()
    monkeypatch.setattr("urllib.request.urlopen", http_mock)
    ops_view.summarize_alerts()
    ops_view.summarize_notifications()
    ops_view.get_runner_health()
    http_mock.assert_not_called()


def test_t_json_secret_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()
    payload = {"api_key": TEST_INGEST_API_KEY, "safe": "ok"}
    text = json.dumps(payload, ensure_ascii=False)
    from pricebrain_app.crawler.logging_utils import redact_secrets

    redacted = redact_secrets(text, collect_secrets_for_redaction())
    assert TEST_INGEST_API_KEY not in redacted
    assert "safe" in redacted


def test_u_authorization_header_masking() -> None:
    from pricebrain_app.crawler.logging_utils import redact_secrets

    secret = "Bearer super-secret-token"
    text = json.dumps({"Authorization": secret})
    redacted = redact_secrets(text, [secret])
    assert secret not in redacted


def test_v_env_isolation_for_json_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRICEBRAIN_INGEST_API_KEY", raising=False)
    clear_settings_cache()
    settings = get_settings()
    assert settings.pricebrain_ingest_api_key is None or settings.pricebrain_ingest_api_key != "must-not-leak"


def test_cli_help_smoke() -> None:
    for main in (
        list_price_alerts.main,
        show_price_alert.main,
        show_price_alert_status.main,
        show_notification_status.main,
        show_price_alert_runner.main,
    ):
        with pytest.raises(SystemExit) as exc:
            main(["--help"])
        assert exc.value.code == 0


def test_list_price_alerts_filters(
    alert_repo: PriceAlertRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        enabled=True,
        now=NOW,
    )
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_UP,
        threshold=1,
        enabled=False,
        now=NOW,
    )
    monkeypatch.setattr(list_price_alerts, "build_price_alert_repository", lambda: alert_repo)
    assert list_price_alerts.main(["--enabled", "--json"]) == 0


def test_show_price_alert_status_json(
    alert_repo: PriceAlertRepository,
    target_repo: CrawlTargetRepository,
    price_view: PriceOperationsView,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    view = AlertOperationsView(alert_repo, target_repo, price_view)
    monkeypatch.setattr(show_price_alert_status, "build_alert_operations_view", lambda: view)
    assert show_price_alert_status.main(["--json"]) == 0


def test_show_price_alert_not_found(
    alert_repo: PriceAlertRepository,
    target_repo: CrawlTargetRepository,
    price_view: PriceOperationsView,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = AlertOperationsView(alert_repo, target_repo, price_view)
    monkeypatch.setattr(show_price_alert, "build_alert_operations_view", lambda: view)
    assert show_price_alert.main(["--alert-id", "missing"]) == 1


def test_price_lookup_error_isolated(
    alert_repo: PriceAlertRepository,
    ops_view: AlertOperationsView,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    monkeypatch.setattr(
        ops_view._prices,
        "get_current_price",
        MagicMock(side_effect=RuntimeError("price read failed")),
    )
    snapshots = ops_view.list_alert_snapshots()
    assert len(snapshots) == 1
    assert snapshots[0].read_error == "price read failed"
