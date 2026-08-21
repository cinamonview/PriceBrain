"""Audit event history read-only operations tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.crawler.audit_event_store import (
    get_audit_event_store,
    record_audit_events_from_cycle,
    reset_audit_event_store,
)
from pricebrain_app.crawler.audit_operations_models import (
    AuditEvent,
    AuditEventFilter,
    AuditEventType,
    parse_audit_event,
)
from pricebrain_app.crawler.audit_operations_view import AuditOperationsView
from pricebrain_app.crawler.alert_ops_health_store import reset_alert_ops_health_store
from pricebrain_app.crawler.notification_adapter import FakeNotificationAdapter, FailingNotificationAdapter
from pricebrain_app.crawler.notification_dispatcher import NotificationDispatcher
from pricebrain_app.crawler.notification_models import NotificationChannel, NotificationSendStatus
from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction
from pricebrain_app.crawler.price_alert_models import AlertEvaluationOutcome, PriceAlertType
from pricebrain_app.crawler.price_alert_repository import PriceAlertRepository
from pricebrain_app.crawler.price_alert_runner import PriceAlertRunner, PriceAlertRunnerCycleResult
from pricebrain_app.crawler.price_alert_service import PriceAlertService
from pricebrain_app.crawler.price_operations_view import PriceOperationsView
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.listing_repository import build_listing_document_id
from pricebrain_app.scripts import (
    list_audit_events,
    show_price_alert_audit,
    show_runner_audit,
    show_target_audit,
)
from pricebrain_app.tests.conftest import TEST_INGEST_API_KEY
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
TARGET_ID = "ssg_1000832367906"
PRODUCT_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
LISTING_ID = build_listing_document_id("ssg", "1000832367906")


@pytest.fixture(autouse=True)
def _reset_stores() -> None:
    reset_alert_ops_health_store()
    reset_audit_event_store()


@pytest.fixture
def audit_db() -> FakeFirestoreClient:
    return FakeFirestoreClient()


@pytest.fixture
def alert_repo(audit_db: FakeFirestoreClient) -> PriceAlertRepository:
    return PriceAlertRepository(audit_db)


@pytest.fixture
def target_repo(audit_db: FakeFirestoreClient) -> CrawlTargetRepository:
    return CrawlTargetRepository(audit_db)


@pytest.fixture
def price_view(audit_db: FakeFirestoreClient, target_repo: CrawlTargetRepository) -> PriceOperationsView:
    return PriceOperationsView(target_repo, audit_db)


@pytest.fixture
def audit_view(alert_repo: PriceAlertRepository) -> AuditOperationsView:
    return AuditOperationsView(alert_repo, event_store=get_audit_event_store())


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


def _append_event(**kwargs) -> None:
    get_audit_event_store().append(
        AuditEvent(
            event_id=kwargs.pop("event_id"),
            event_type=kwargs.pop("event_type"),
            occurred_at=kwargs.pop("occurred_at", NOW),
            **kwargs,
        )
    )


def test_a_event_parsing() -> None:
    event, error = parse_audit_event(
        {
            "event_id": "evt-1",
            "event_type": "ALERT_TRIGGERED",
            "occurred_at": NOW.isoformat(),
            "alert_id": "a1",
            "target_id": TARGET_ID,
            "price": 1490000,
        }
    )
    assert error is None
    assert event is not None
    assert event.event_type is AuditEventType.ALERT_TRIGGERED


def test_b_malformed_event_isolation(audit_view: AuditOperationsView) -> None:
    store = get_audit_event_store()
    store.append_raw({"event_id": "", "event_type": "ALERT_TRIGGERED"})
    _append_event(event_id="good-1", event_type=AuditEventType.ALERT_EVALUATED, alert_id="a1")
    summary = audit_view.summarize_events()
    assert summary.read_errors >= 1
    events = audit_view.list_events()
    assert any(item.read_error for item in events)
    assert any(item.event and item.event.event_id == "good-1" for item in events)


def test_c_unknown_event_type() -> None:
    event, error = parse_audit_event(
        {
            "event_id": "evt-unknown",
            "event_type": "NOT_A_REAL_TYPE",
            "occurred_at": NOW.isoformat(),
        }
    )
    assert error is None
    assert event is not None
    assert event.event_type is AuditEventType.UNKNOWN


def test_d_missing_timestamp() -> None:
    event, error = parse_audit_event(
        {
            "event_id": "evt-no-ts",
            "event_type": "ALERT_EVALUATED",
        }
    )
    assert error is None
    assert event is not None
    assert event.occurred_at is not None


def test_e_alert_filter(audit_view: AuditOperationsView) -> None:
    _append_event(event_id="e1", event_type=AuditEventType.ALERT_TRIGGERED, alert_id="a1", target_id=TARGET_ID)
    _append_event(event_id="e2", event_type=AuditEventType.ALERT_EVALUATED, alert_id="a2", target_id=TARGET_ID)
    events = audit_view.list_events(filters=AuditEventFilter(alert_id="a1"))
    assert len(events) == 1
    assert events[0].event is not None
    assert events[0].event.alert_id == "a1"


def test_f_target_filter(audit_view: AuditOperationsView) -> None:
    _append_event(event_id="e1", event_type=AuditEventType.ALERT_TRIGGERED, alert_id="a1", target_id=TARGET_ID)
    _append_event(
        event_id="e2",
        event_type=AuditEventType.ALERT_EVALUATED,
        alert_id="a2",
        target_id="other_target",
    )
    events = audit_view.list_events(filters=AuditEventFilter(target_id=TARGET_ID))
    assert len(events) == 1
    assert events[0].event is not None
    assert events[0].event.target_id == TARGET_ID


def test_g_event_type_filter(audit_view: AuditOperationsView) -> None:
    _append_event(event_id="e1", event_type=AuditEventType.ALERT_TRIGGERED, alert_id="a1")
    _append_event(event_id="e2", event_type=AuditEventType.NOTIFICATION_SENT, alert_id="a1", channel="FAKE")
    events = audit_view.list_events(filters=AuditEventFilter(event_type="ALERT_TRIGGERED"))
    assert len(events) == 1
    assert events[0].event is not None
    assert events[0].event.event_type is AuditEventType.ALERT_TRIGGERED


def test_h_failure_filter(audit_view: AuditOperationsView) -> None:
    _append_event(event_id="e1", event_type=AuditEventType.NOTIFICATION_FAILED, alert_id="a1", status="FAILED")
    _append_event(event_id="e2", event_type=AuditEventType.NOTIFICATION_SENT, alert_id="a1", status="SENT")
    events = audit_view.list_events(filters=AuditEventFilter(failures_only=True))
    assert len(events) == 1
    assert events[0].event is not None
    assert events[0].event.event_type is AuditEventType.NOTIFICATION_FAILED


def test_i_recent_filter(audit_view: AuditOperationsView) -> None:
    for index in range(5):
        _append_event(
            event_id=f"evt-{index}",
            event_type=AuditEventType.ALERT_EVALUATED,
            occurred_at=NOW + timedelta(minutes=index),
            alert_id=f"a{index}",
        )
    events = audit_view.list_events(filters=AuditEventFilter(recent=2))
    assert len(events) == 2


def test_j_json_output(audit_view: AuditOperationsView) -> None:
    _append_event(event_id="e1", event_type=AuditEventType.ALERT_TRIGGERED, alert_id="a1")
    payload = audit_view.summarize_events().to_dict()
    assert payload["total"] == 1
    assert "by_type" in payload


def test_k_secret_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()
    from pricebrain_app.crawler.logging_utils import redact_secrets

    text = json.dumps({"Authorization": f"Bearer {TEST_INGEST_API_KEY}"})
    redacted = redact_secrets(text, collect_secrets_for_redaction())
    assert TEST_INGEST_API_KEY not in redacted


def test_l_read_only_no_firestore_writes(
    alert_repo: PriceAlertRepository,
    audit_db: FakeFirestoreClient,
    audit_view: AuditOperationsView,
) -> None:
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    writes_after_seed = len(audit_db._data)
    _append_event(event_id="e1", event_type=AuditEventType.ALERT_TRIGGERED, alert_id="a1")
    audit_view.list_events()
    audit_view.summarize_events()
    audit_view.list_runner_audit()
    assert len(audit_db._data) == writes_after_seed


def test_m_no_http(audit_view: AuditOperationsView, monkeypatch: pytest.MonkeyPatch) -> None:
    http_mock = MagicMock()
    monkeypatch.setattr("urllib.request.urlopen", http_mock)
    audit_view.list_events()
    http_mock.assert_not_called()


def test_n_no_notification_dispatch(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
    audit_view: AuditOperationsView,
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
    audit_view.list_events()
    dispatcher.dispatch.assert_not_called()


def test_o_no_runner_execution(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
    audit_view: AuditOperationsView,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_once = MagicMock()
    monkeypatch.setattr(PriceAlertRunner, "run_once", run_once)
    audit_view.list_runner_audit()
    run_once.assert_not_called()


def test_p_alert_lifecycle(
    alert_repo: PriceAlertRepository,
    target_repo: CrawlTargetRepository,
    audit_db: FakeFirestoreClient,
    audit_view: AuditOperationsView,
) -> None:
    _seed_target(target_repo)
    _seed_listing(audit_db, current=1_490_000, previous=1_599_000)
    alert = alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW - timedelta(hours=1),
    )
    PriceAlertRunner(_service(alert_repo, PriceOperationsView(target_repo, audit_db))).run_once(now=NOW)
    events = audit_view.list_alert_audit(alert.alert_id)
    types = [item.event.event_type for item in events if item.event is not None]
    assert AuditEventType.ALERT_CREATED in types
    assert AuditEventType.ALERT_TRIGGERED in types
    assert AuditEventType.NOTIFICATION_SENT in types


def test_q_target_lifecycle(
    alert_repo: PriceAlertRepository,
    target_repo: CrawlTargetRepository,
    audit_db: FakeFirestoreClient,
    audit_view: AuditOperationsView,
) -> None:
    _seed_target(target_repo)
    _seed_listing(audit_db, current=1_490_000, previous=1_599_000)
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    PriceAlertRunner(_service(alert_repo, PriceOperationsView(target_repo, audit_db))).run_once(now=NOW)
    events = audit_view.list_target_audit(TARGET_ID)
    assert len(events) >= 2
    assert events[0].event is not None
    assert events[-1].event is not None
    assert events[0].event.occurred_at <= events[-1].event.occurred_at


def test_r_runner_lifecycle(
    alert_repo: PriceAlertRepository,
    target_repo: CrawlTargetRepository,
    audit_db: FakeFirestoreClient,
    audit_view: AuditOperationsView,
) -> None:
    _seed_target(target_repo)
    _seed_listing(audit_db, current=1_490_000, previous=1_599_000)
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    PriceAlertRunner(_service(alert_repo, PriceOperationsView(target_repo, audit_db))).run_once(now=NOW)
    events = audit_view.list_runner_audit(recent=5)
    assert len(events) == 1
    assert events[0].event is not None
    assert events[0].event.event_type is AuditEventType.RUNNER_CYCLE_COMPLETED


def test_s_event_ordering(audit_view: AuditOperationsView) -> None:
    _append_event(
        event_id="b-event",
        event_type=AuditEventType.ALERT_EVALUATED,
        occurred_at=NOW,
        alert_id="a1",
    )
    _append_event(
        event_id="a-event",
        event_type=AuditEventType.ALERT_TRIGGERED,
        occurred_at=NOW,
        alert_id="a2",
    )
    events = audit_view.list_events()
    assert events[0].event is not None
    assert events[0].event.event_id == "a-event"
    assert events[1].event is not None
    assert events[1].event.event_id == "b-event"


def test_t_failure_isolation_returns_valid_events(audit_view: AuditOperationsView) -> None:
    store = get_audit_event_store()
    store.append_raw({"bad": True})
    _append_event(event_id="valid-1", event_type=AuditEventType.ALERT_EVALUATED, alert_id="a1")
    events = audit_view.list_events()
    assert any(item.read_error for item in events)
    assert any(item.event and item.event.event_id == "valid-1" for item in events)


def test_runner_cycle_failed_event(
    alert_repo: PriceAlertRepository,
    target_repo: CrawlTargetRepository,
    audit_db: FakeFirestoreClient,
    audit_view: AuditOperationsView,
) -> None:
    _seed_target(target_repo)
    _seed_listing(audit_db, current=1_490_000, previous=1_599_000)
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    PriceAlertRunner(_service(alert_repo, PriceOperationsView(target_repo, audit_db), failing=True)).run_once(
        now=NOW
    )
    events = audit_view.list_runner_audit(failures_only=True)
    assert len(events) >= 1
    assert events[0].event is not None
    assert events[0].event.event_type is AuditEventType.RUNNER_CYCLE_FAILED


def test_record_audit_events_from_cycle_direct() -> None:
    cycle = PriceAlertRunnerCycleResult(
        cycle_started_at=NOW,
        cycle_finished_at=NOW + timedelta(seconds=1),
        total_alerts=1,
        evaluated=1,
        triggered=0,
        skipped=0,
        invalid=0,
        not_triggered=1,
        notification_sent=0,
        notification_failed=0,
    )
    record_audit_events_from_cycle(cycle, results=[])
    events = get_audit_event_store().list_raw()
    assert len(events) == 1
    assert events[0]["event_type"] == AuditEventType.RUNNER_CYCLE_COMPLETED.value


def test_cli_help_smoke() -> None:
    for main in (
        list_audit_events.main,
        show_price_alert_audit.main,
        show_target_audit.main,
        show_runner_audit.main,
    ):
        with pytest.raises(SystemExit) as exc:
            main(["--help"])
        assert exc.value.code == 0


def test_cli_list_json(
    audit_view: AuditOperationsView,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _append_event(event_id="e1", event_type=AuditEventType.ALERT_TRIGGERED, alert_id="a1")
    monkeypatch.setattr(list_audit_events, "build_audit_operations_view", lambda: audit_view)
    assert list_audit_events.main(["--json"]) == 0


def test_malformed_metadata_isolation() -> None:
    event, error = parse_audit_event(
        {
            "event_id": "evt-meta",
            "event_type": "ALERT_EVALUATED",
            "occurred_at": NOW.isoformat(),
            "metadata": "not-a-dict",
        }
    )
    assert error is None
    assert event is not None
    assert event.metadata == {}
