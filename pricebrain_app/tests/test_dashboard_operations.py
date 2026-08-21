"""Operations dashboard read-only tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.crawler.alert_operations_view import AlertOperationsView
from pricebrain_app.crawler.audit_event_store import reset_audit_event_store
from pricebrain_app.crawler.audit_operations_view import AuditOperationsView
from pricebrain_app.crawler.dashboard_health import classify_dashboard_health, runner_cycle_status
from pricebrain_app.crawler.dashboard_operations_models import (
    AlertDashboardSummary,
    AuditDashboardSummary,
    CrawlerDashboardSummary,
    DashboardFilter,
    DashboardHealthStatus,
    NotificationDashboardSummary,
    PriceDashboardSummary,
    RunnerDashboardSummary,
)
from pricebrain_app.crawler.dashboard_operations_view import DashboardOperationsView
from pricebrain_app.crawler.alert_ops_health_store import reset_alert_ops_health_store
from pricebrain_app.crawler.notification_adapter import FakeNotificationAdapter, FailingNotificationAdapter
from pricebrain_app.crawler.notification_dispatcher import NotificationDispatcher
from pricebrain_app.crawler.notification_models import NotificationChannel
from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction
from pricebrain_app.crawler.operations_view import CrawlerOperationsView
from pricebrain_app.crawler.price_alert_models import PriceAlertType
from pricebrain_app.crawler.price_alert_repository import PriceAlertRepository
from pricebrain_app.crawler.price_alert_runner import PriceAlertRunner
from pricebrain_app.crawler.price_alert_service import PriceAlertService
from pricebrain_app.crawler.price_operations_view import PriceOperationsView
from pricebrain_app.crawler.results import CrawlerResult, CrawlerStatus
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.targets import CRAWLER_TARGETS_COLLECTION
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.listing_repository import build_listing_document_id
from pricebrain_app.scripts import show_pricebrain_dashboard
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
def dash_db() -> FakeFirestoreClient:
    return FakeFirestoreClient()


@pytest.fixture
def alert_repo(dash_db: FakeFirestoreClient) -> PriceAlertRepository:
    return PriceAlertRepository(dash_db)


@pytest.fixture
def target_repo(dash_db: FakeFirestoreClient) -> CrawlTargetRepository:
    return CrawlTargetRepository(dash_db)


@pytest.fixture
def crawler_view(dash_db: FakeFirestoreClient, target_repo: CrawlTargetRepository) -> CrawlerOperationsView:
    return CrawlerOperationsView(target_repo, dash_db)


@pytest.fixture
def price_view(dash_db: FakeFirestoreClient, target_repo: CrawlTargetRepository) -> PriceOperationsView:
    return PriceOperationsView(target_repo, dash_db)


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


@pytest.fixture
def dashboard_view(
    crawler_view: CrawlerOperationsView,
    price_view: PriceOperationsView,
    alert_view: AlertOperationsView,
    audit_view: AuditOperationsView,
) -> DashboardOperationsView:
    return DashboardOperationsView(crawler_view, price_view, alert_view, audit_view)


def _seed_target(repo: CrawlTargetRepository, *, enabled: bool = True) -> None:
    repo.merge_catalog(
        mall_id="ssg",
        product_url=PRODUCT_URL,
        product_name="GPU",
        category="gpu",
        tags=["zotac"],
        priority=100,
        now=NOW,
    )
    if not enabled:
        target = repo.get(TARGET_ID)
        if target is not None:
            repo.set_enabled(TARGET_ID, enabled=False)


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


def _mark_failed(repo: CrawlTargetRepository, *, error_code: str = "SSG_ACCESS_DENIED") -> None:
    repo.update_after_crawl(
        TARGET_ID,
        result=CrawlerResult(status=CrawlerStatus.HTTP_ERROR, mall_id="ssg", message=error_code),
        next_crawl_at=NOW,
        crawled_at=NOW,
    )
    repo._db.collection(CRAWLER_TARGETS_COLLECTION).document(TARGET_ID).set(
        {
            "last_status": "HTTP_ERROR",
            "last_error_code": error_code,
            "last_error_message": error_code,
        },
        merge=True,
    )


def _healthy_sections() -> tuple[
    CrawlerDashboardSummary,
    PriceDashboardSummary,
    AlertDashboardSummary,
    NotificationDashboardSummary,
    RunnerDashboardSummary,
    AuditDashboardSummary,
]:
    return (
        CrawlerDashboardSummary(total_targets=1, enabled_targets=1, failed_targets=0),
        PriceDashboardSummary(targets=1, with_price=1),
        AlertDashboardSummary(total=1, enabled=1),
        NotificationDashboardSummary(sent=1),
        RunnerDashboardSummary(last_cycle_status="SUCCESS", recent_cycles=1),
        AuditDashboardSummary(recent_events=1),
    )


def test_a_healthy_dashboard() -> None:
    crawler, price, alerts, notifications, runner, audit = _healthy_sections()
    summary = classify_dashboard_health(
        crawler=crawler,
        price=price,
        alerts=alerts,
        notifications=notifications,
        runner=runner,
        audit=audit,
    )
    assert summary.health is DashboardHealthStatus.HEALTHY


def test_b_partial_crawler_failure_still_returns_dashboard(
    dashboard_view: DashboardOperationsView,
    target_repo: CrawlTargetRepository,
    dash_db: FakeFirestoreClient,
) -> None:
    _seed_target(target_repo)
    _mark_failed(target_repo)
    snapshot = dashboard_view.build_dashboard_snapshot(now=NOW)
    assert snapshot.crawler.failed_targets >= 1
    assert snapshot.price.read_error is None
    assert snapshot.summary.health is not DashboardHealthStatus.CRITICAL


def test_c_ssg_access_denied_not_critical(
    dashboard_view: DashboardOperationsView,
    target_repo: CrawlTargetRepository,
    dash_db: FakeFirestoreClient,
) -> None:
    _seed_target(target_repo)
    _mark_failed(target_repo, error_code="SSG_ACCESS_DENIED")
    snapshot = dashboard_view.build_dashboard_snapshot(now=NOW)
    assert snapshot.crawler.ssg_access_denied >= 1
    assert snapshot.summary.health is DashboardHealthStatus.DEGRADED
    assert snapshot.summary.health is not DashboardHealthStatus.CRITICAL


def test_d_notification_failed_degraded() -> None:
    crawler, price, alerts, notifications, runner, audit = _healthy_sections()
    notifications = NotificationDashboardSummary(sent=1, failed=1)
    summary = classify_dashboard_health(
        crawler=crawler,
        price=price,
        alerts=alerts,
        notifications=notifications,
        runner=runner,
        audit=audit,
    )
    assert summary.health is DashboardHealthStatus.DEGRADED


def test_e_runner_cycle_failed_degraded() -> None:
    crawler, price, alerts, notifications, _, audit = _healthy_sections()
    runner = RunnerDashboardSummary(last_cycle_status="FAILED", recent_cycles=1, recent_failed_cycles=1)
    summary = classify_dashboard_health(
        crawler=crawler,
        price=price,
        alerts=alerts,
        notifications=notifications,
        runner=runner,
        audit=audit,
    )
    assert summary.health is DashboardHealthStatus.DEGRADED


def test_f_audit_malformed_event_dashboard_continues(
    audit_view: AuditOperationsView,
    dashboard_view: DashboardOperationsView,
) -> None:
    from pricebrain_app.crawler.audit_event_store import get_audit_event_store

    get_audit_event_store().append_raw({"bad": True})
    snapshot = dashboard_view.build_dashboard_snapshot(now=NOW)
    assert snapshot.audit.read_error is not None or snapshot.audit.recent_events >= 0
    assert snapshot.crawler.read_error is None


def test_g_price_section_failure_isolated(dashboard_view: DashboardOperationsView) -> None:
    dashboard_view._build_price = MagicMock(return_value=PriceDashboardSummary(read_error="price failed"))  # type: ignore[method-assign]
    snapshot = dashboard_view.build_dashboard_snapshot(now=NOW)
    assert snapshot.price.read_error == "price failed"
    assert snapshot.crawler.read_error is None


def test_h_alert_section_failure_isolated(dashboard_view: DashboardOperationsView) -> None:
    dashboard_view._build_alerts = MagicMock(return_value=AlertDashboardSummary(read_error="alert failed"))  # type: ignore[method-assign]
    snapshot = dashboard_view.build_dashboard_snapshot(now=NOW)
    assert snapshot.alerts.read_error == "alert failed"
    assert snapshot.runner.read_error is None


def test_i_no_firestore_writes(
    dashboard_view: DashboardOperationsView,
    dash_db: FakeFirestoreClient,
    target_repo: CrawlTargetRepository,
    alert_repo: PriceAlertRepository,
) -> None:
    _seed_target(target_repo)
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    writes_after_seed = len(dash_db._data)
    dashboard_view.build_dashboard_snapshot(now=NOW)
    assert len(dash_db._data) == writes_after_seed


def test_j_no_http(dashboard_view: DashboardOperationsView, monkeypatch: pytest.MonkeyPatch) -> None:
    http_mock = MagicMock()
    monkeypatch.setattr("urllib.request.urlopen", http_mock)
    dashboard_view.build_dashboard_snapshot(now=NOW)
    http_mock.assert_not_called()


def test_k_no_crawler_execution(dashboard_view: DashboardOperationsView, monkeypatch: pytest.MonkeyPatch) -> None:
    crawl_mock = MagicMock()
    monkeypatch.setattr("pricebrain_app.crawler.adapters.ssg.SSGCrawler.crawl", crawl_mock)
    dashboard_view.build_dashboard_snapshot(now=NOW)
    crawl_mock.assert_not_called()


def test_l_no_notification_dispatch(
    dashboard_view: DashboardOperationsView,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch = MagicMock()
    monkeypatch.setattr(
        "pricebrain_app.crawler.notification_dispatcher.NotificationDispatcher.dispatch",
        dispatch,
    )
    dashboard_view.build_dashboard_snapshot(now=NOW)
    dispatch.assert_not_called()


def test_m_no_alert_trigger(
    alert_repo: PriceAlertRepository,
    dashboard_view: DashboardOperationsView,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mark_triggered = MagicMock(side_effect=alert_repo.mark_triggered)
    monkeypatch.setattr(alert_repo, "mark_triggered", mark_triggered)
    dashboard_view.build_dashboard_snapshot(now=NOW)
    mark_triggered.assert_not_called()


def test_n_no_runner_execution(dashboard_view: DashboardOperationsView, monkeypatch: pytest.MonkeyPatch) -> None:
    run_once = MagicMock()
    monkeypatch.setattr(PriceAlertRunner, "run_once", run_once)
    dashboard_view.build_dashboard_snapshot(now=NOW)
    run_once.assert_not_called()


def test_o_json_secret_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()
    from pricebrain_app.crawler.logging_utils import redact_secrets

    text = json.dumps({"api_key": TEST_INGEST_API_KEY})
    redacted = redact_secrets(text, collect_secrets_for_redaction())
    assert TEST_INGEST_API_KEY not in redacted


def test_p_authorization_header_masking() -> None:
    from pricebrain_app.crawler.logging_utils import redact_secrets

    secret = "Bearer secret-token"
    redacted = redact_secrets(json.dumps({"Authorization": secret}), [secret])
    assert secret not in redacted


def test_q_cli_help() -> None:
    with pytest.raises(SystemExit) as exc:
        show_pricebrain_dashboard.main(["--help"])
    assert exc.value.code == 0


def test_r_cli_json(dashboard_view: DashboardOperationsView, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(show_pricebrain_dashboard, "build_dashboard_operations_view", lambda: dashboard_view)
    assert show_pricebrain_dashboard.main(["--json"]) == 0


def test_s_cli_recent(dashboard_view: DashboardOperationsView, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(show_pricebrain_dashboard, "build_dashboard_operations_view", lambda: dashboard_view)
    assert show_pricebrain_dashboard.main(["--recent", "3", "--json"]) == 0


def test_t_cli_failures(dashboard_view: DashboardOperationsView, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(show_pricebrain_dashboard, "build_dashboard_operations_view", lambda: dashboard_view)
    assert show_pricebrain_dashboard.main(["--failures", "--json"]) == 0


def test_u_cli_category_gpu(
    dashboard_view: DashboardOperationsView,
    target_repo: CrawlTargetRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_target(target_repo)
    monkeypatch.setattr(show_pricebrain_dashboard, "build_dashboard_operations_view", lambda: dashboard_view)
    assert show_pricebrain_dashboard.main(["--category", "gpu", "--json"]) == 0


def test_v_cli_mall_ssg(
    dashboard_view: DashboardOperationsView,
    target_repo: CrawlTargetRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_target(target_repo)
    monkeypatch.setattr(show_pricebrain_dashboard, "build_dashboard_operations_view", lambda: dashboard_view)
    assert show_pricebrain_dashboard.main(["--mall", "ssg", "--json"]) == 0


def test_w_health_classification_pure_function() -> None:
    assert runner_cycle_status(
        last_failed_cycle_at=None,
        last_successful_cycle_at=NOW,
        errors=(),
        notification_failed=0,
    ) == "SUCCESS"
    assert classify_dashboard_health(
        crawler=CrawlerDashboardSummary(),
        price=PriceDashboardSummary(),
        alerts=AlertDashboardSummary(),
        notifications=NotificationDashboardSummary(),
        runner=RunnerDashboardSummary(),
        audit=AuditDashboardSummary(),
    ).health is DashboardHealthStatus.UNKNOWN


def test_x_empty_dataset_unknown(dashboard_view: DashboardOperationsView) -> None:
    snapshot = dashboard_view.build_dashboard_snapshot(now=NOW)
    assert snapshot.summary.health is DashboardHealthStatus.UNKNOWN


def test_integration_runner_audit_on_dashboard(
    dashboard_view: DashboardOperationsView,
    target_repo: CrawlTargetRepository,
    dash_db: FakeFirestoreClient,
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
) -> None:
    _seed_target(target_repo)
    _seed_listing(dash_db, current=1_490_000, previous=1_599_000)
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    service = PriceAlertService(
        alert_repo,
        price_view,
        notification_dispatcher=NotificationDispatcher({NotificationChannel.FAKE: FakeNotificationAdapter()}),
        default_channel=NotificationChannel.FAKE,
        notifications_enabled_override=True,
    )
    PriceAlertRunner(service).run_once(now=NOW)
    snapshot = dashboard_view.build_dashboard_snapshot(now=NOW)
    assert snapshot.runner.recent_cycles >= 1
    assert snapshot.audit.recent_events >= 1


def test_repeated_runner_failure_critical() -> None:
    crawler, price, alerts, notifications, _, audit = _healthy_sections()
    runner = RunnerDashboardSummary(
        last_cycle_status="FAILED",
        recent_cycles=3,
        recent_failed_cycles=2,
    )
    summary = classify_dashboard_health(
        crawler=crawler,
        price=price,
        alerts=alerts,
        notifications=notifications,
        runner=runner,
        audit=audit,
    )
    assert summary.health is DashboardHealthStatus.CRITICAL


def test_dashboard_filter_recent_propagates(dashboard_view: DashboardOperationsView) -> None:
    snapshot = dashboard_view.build_dashboard_snapshot(
        filters=DashboardFilter(recent=2),
        now=NOW,
    )
    assert len(snapshot.audit.event_snapshots) <= 2
