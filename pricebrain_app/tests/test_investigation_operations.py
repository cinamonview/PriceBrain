"""Dashboard investigation read-only tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.crawler.alert_operations_view import AlertOperationsView
from pricebrain_app.crawler.alert_ops_health_store import reset_alert_ops_health_store
from pricebrain_app.crawler.audit_event_store import reset_audit_event_store
from pricebrain_app.crawler.audit_operations_view import AuditOperationsView
from pricebrain_app.crawler.dashboard_health import classify_dashboard_health
from pricebrain_app.crawler.dashboard_operations_models import (
    AlertDashboardSummary,
    AuditDashboardSummary,
    CrawlerDashboardSummary,
    DashboardFilter,
    DashboardHealthStatus,
    DashboardSummary,
    NotificationDashboardSummary,
    PriceBrainDashboardSnapshot,
    PriceDashboardSummary,
    RunnerDashboardSummary,
)
from pricebrain_app.crawler.dashboard_operations_view import DashboardOperationsView
from pricebrain_app.crawler.investigation_operations_models import (
    DashboardInvestigationSnapshot,
    InvestigationFilter,
    InvestigationFinding,
    InvestigationSeverity,
    sort_findings,
    summarize_findings,
)
from pricebrain_app.crawler.investigation_operations_view import InvestigationOperationsView
from pricebrain_app.crawler.investigation_rules import analyze_dashboard_snapshot
from pricebrain_app.crawler.notification_adapter import FakeNotificationAdapter
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
from pricebrain_app.scripts import show_pricebrain_investigation
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
def inv_db() -> FakeFirestoreClient:
    return FakeFirestoreClient()


@pytest.fixture
def alert_repo(inv_db: FakeFirestoreClient) -> PriceAlertRepository:
    return PriceAlertRepository(inv_db)


@pytest.fixture
def target_repo(inv_db: FakeFirestoreClient) -> CrawlTargetRepository:
    return CrawlTargetRepository(inv_db)


@pytest.fixture
def dashboard_view(
    inv_db: FakeFirestoreClient,
    target_repo: CrawlTargetRepository,
    alert_repo: PriceAlertRepository,
) -> DashboardOperationsView:
    price_view = PriceOperationsView(target_repo, inv_db)
    return DashboardOperationsView(
        CrawlerOperationsView(target_repo, inv_db),
        price_view,
        AlertOperationsView(alert_repo, target_repo, price_view),
        AuditOperationsView(alert_repo),
    )


@pytest.fixture
def investigation_view(dashboard_view: DashboardOperationsView) -> InvestigationOperationsView:
    return InvestigationOperationsView(dashboard_view    )


def summarize_from(findings: list[InvestigationFinding]):
    return summarize_findings(findings)


def _snapshot(**overrides) -> PriceBrainDashboardSnapshot:
    crawler = CrawlerDashboardSummary()
    price = PriceDashboardSummary()
    alerts = AlertDashboardSummary()
    notifications = NotificationDashboardSummary()
    runner = RunnerDashboardSummary()
    audit = AuditDashboardSummary()
    summary = DashboardSummary(health=DashboardHealthStatus.HEALTHY)
    for key, value in overrides.items():
        if key == "crawler":
            crawler = value
        elif key == "price":
            price = value
        elif key == "alerts":
            alerts = value
        elif key == "notifications":
            notifications = value
        elif key == "runner":
            runner = value
        elif key == "audit":
            audit = value
        elif key == "summary":
            summary = value
    return PriceBrainDashboardSnapshot(
        generated_at=NOW,
        summary=summary,
        crawler=crawler,
        price=price,
        alerts=alerts,
        notifications=notifications,
        runner=runner,
        audit=audit,
    )


def test_ssg_access_denied_warning() -> None:
    findings = analyze_dashboard_snapshot(
        _snapshot(crawler=CrawlerDashboardSummary(ssg_access_denied=3, failed_targets=3))
    )
    assert any(item.code == "CRAWLER_ACCESS_DENIED" and item.severity is InvestigationSeverity.WARNING for item in findings)


def test_repeated_runner_failure_critical() -> None:
    findings = analyze_dashboard_snapshot(
        _snapshot(runner=RunnerDashboardSummary(recent_failed_cycles=2, last_cycle_status="FAILED"))
    )
    assert any(item.code == "RUNNER_CYCLE_FAILURE_REPEATED" and item.severity is InvestigationSeverity.CRITICAL for item in findings)


def test_notification_failure_error() -> None:
    findings = analyze_dashboard_snapshot(
        _snapshot(notifications=NotificationDashboardSummary(failed=1))
    )
    assert any(item.code == "NOTIFICATION_FAILURE" and item.severity is InvestigationSeverity.ERROR for item in findings)


def test_repeated_notification_failure_critical() -> None:
    findings = analyze_dashboard_snapshot(
        _snapshot(
            notifications=NotificationDashboardSummary(
                failed=2,
                recent_failures=({"alert_id": "a1"}, {"alert_id": "a2"}),
            )
        )
    )
    assert any(
        item.code == "NOTIFICATION_FAILURE_REPEATED" and item.severity is InvestigationSeverity.CRITICAL
        for item in findings
    )


def test_price_no_history_warning() -> None:
    findings = analyze_dashboard_snapshot(_snapshot(price=PriceDashboardSummary(no_history=5, targets=5)))
    assert any(item.code == "PRICE_NO_HISTORY" for item in findings)


def test_alert_read_error() -> None:
    findings = analyze_dashboard_snapshot(_snapshot(alerts=AlertDashboardSummary(read_error="bad alert")))
    assert any(item.code == "ALERT_READ_ERROR" for item in findings)


def test_audit_read_error() -> None:
    findings = analyze_dashboard_snapshot(_snapshot(audit=AuditDashboardSummary(read_error="2 malformed audit events")))
    assert any(item.code == "AUDIT_READ_ERROR" for item in findings)


def test_malformed_data_isolation(investigation_view: InvestigationOperationsView) -> None:
    investigation_view._dashboard.build_dashboard_snapshot = MagicMock(  # type: ignore[method-assign]
        return_value=_snapshot(
            crawler=CrawlerDashboardSummary(read_error="crawler failed"),
            price=PriceDashboardSummary(no_history=1),
        )
    )
    snapshot = investigation_view.investigate_dashboard()
    codes = {item.code for item in snapshot.findings}
    assert "CRAWLER_HTTP_ERROR" in codes
    assert "PRICE_NO_HISTORY" in codes


def test_area_filtering(investigation_view: InvestigationOperationsView) -> None:
    investigation_view._dashboard.build_dashboard_snapshot = MagicMock(  # type: ignore[method-assign]
        return_value=_snapshot(
            crawler=CrawlerDashboardSummary(ssg_access_denied=1, failed_targets=1),
            price=PriceDashboardSummary(no_history=1),
        )
    )
    snapshot = investigation_view.investigate_dashboard()
    crawler_findings = investigation_view.findings_for_area("crawler", snapshot=snapshot)
    assert all(item.area == "crawler" for item in crawler_findings)
    assert not any(item.area == "price" for item in crawler_findings)


def test_target_filtering() -> None:
    snapshot = _snapshot(
        crawler=CrawlerDashboardSummary(
            ssg_access_denied=1,
            failed_targets=1,
            recent_failure_targets=(
                {
                    "target_id": TARGET_ID,
                    "last_error_code": "SSG_ACCESS_DENIED",
                    "last_error_message": "denied",
                },
            ),
        )
    )
    findings = analyze_dashboard_snapshot(snapshot)
    view = InvestigationOperationsView(MagicMock())
    view._last_snapshot = DashboardInvestigationSnapshot(
        generated_at=NOW,
        health=DashboardHealthStatus.DEGRADED,
        summary=summarize_from(findings),
        findings=tuple(findings),
        dashboard_summary=snapshot.summary,
        crawler=snapshot.crawler,
        price=snapshot.price,
        alerts=snapshot.alerts,
        notifications=snapshot.notifications,
        runner=snapshot.runner,
        audit=snapshot.audit,
    )
    filtered = view.findings_for_target(TARGET_ID)
    assert any(item.target_id == TARGET_ID for item in filtered)


def test_alert_filtering() -> None:
    alert_id = "alert-123"
    snapshot = _snapshot(
        notifications=NotificationDashboardSummary(
            failed=1,
            recent_failures=({"alert_id": alert_id, "target_id": TARGET_ID},),
        )
    )
    findings = analyze_dashboard_snapshot(snapshot)
    view = InvestigationOperationsView(MagicMock())
    view._last_snapshot = DashboardInvestigationSnapshot(
        generated_at=NOW,
        health=DashboardHealthStatus.DEGRADED,
        summary=summarize_from(findings),
        findings=tuple(findings),
        dashboard_summary=snapshot.summary,
        crawler=snapshot.crawler,
        price=snapshot.price,
        alerts=snapshot.alerts,
        notifications=snapshot.notifications,
        runner=snapshot.runner,
        audit=snapshot.audit,
    )
    filtered = view.findings_for_alert(alert_id)
    assert any(item.alert_id == alert_id for item in filtered)


def test_severity_sorting() -> None:
    findings = sort_findings(
        [
            InvestigationFinding(
                finding_id="b",
                severity=InvestigationSeverity.WARNING,
                area="crawler",
                code="X",
                title="t",
                message="m",
                occurred_at=NOW,
            ),
            InvestigationFinding(
                finding_id="a",
                severity=InvestigationSeverity.CRITICAL,
                area="runner",
                code="Y",
                title="t",
                message="m",
                occurred_at=NOW,
            ),
        ]
    )
    assert findings[0].severity is InvestigationSeverity.CRITICAL


def test_timestamp_sorting() -> None:
    findings = sort_findings(
        [
            InvestigationFinding(
                finding_id="old",
                severity=InvestigationSeverity.ERROR,
                area="price",
                code="X",
                title="t",
                message="m",
                occurred_at=NOW,
            ),
            InvestigationFinding(
                finding_id="new",
                severity=InvestigationSeverity.ERROR,
                area="price",
                code="Y",
                title="t",
                message="m",
                occurred_at=NOW.replace(hour=13),
            ),
        ]
    )
    assert findings[0].finding_id == "new"


def test_empty_dataset(investigation_view: InvestigationOperationsView) -> None:
    snapshot = investigation_view.investigate_dashboard()
    assert snapshot.health is DashboardHealthStatus.UNKNOWN


def test_dashboard_degraded_investigation(investigation_view: InvestigationOperationsView) -> None:
    investigation_view._dashboard.build_dashboard_snapshot = MagicMock(  # type: ignore[method-assign]
        return_value=_snapshot(
            summary=DashboardSummary(health=DashboardHealthStatus.DEGRADED, reasons=("8 SSG_ACCESS_DENIED targets",)),
            crawler=CrawlerDashboardSummary(ssg_access_denied=8, failed_targets=8, enabled_targets=8),
            price=PriceDashboardSummary(no_history=8, targets=8),
        )
    )
    snapshot = investigation_view.investigate_dashboard()
    assert snapshot.health is DashboardHealthStatus.DEGRADED
    assert any(item.code == "CRAWLER_ACCESS_DENIED" for item in snapshot.findings)


def test_dashboard_critical_investigation() -> None:
    snapshot = _snapshot(
        summary=DashboardSummary(health=DashboardHealthStatus.CRITICAL, reasons=("repeated runner cycle failures",)),
        runner=RunnerDashboardSummary(recent_failed_cycles=2, last_cycle_status="FAILED"),
        notifications=NotificationDashboardSummary(failed=2, recent_failures=({"alert_id": "a1"}, {"alert_id": "a2"})),
    )
    findings = analyze_dashboard_snapshot(snapshot)
    assert any(item.severity is InvestigationSeverity.CRITICAL for item in findings)


def test_firestore_write_regression(
    investigation_view: InvestigationOperationsView,
    inv_db: FakeFirestoreClient,
    target_repo: CrawlTargetRepository,
) -> None:
    target_repo.merge_catalog(
        mall_id="ssg",
        product_url=PRODUCT_URL,
        product_name="GPU",
        category="gpu",
        tags=["zotac"],
        priority=100,
        now=NOW,
    )
    writes = len(inv_db._data)
    investigation_view.investigate_dashboard()
    assert len(inv_db._data) == writes


def test_http_regression(investigation_view: InvestigationOperationsView, monkeypatch: pytest.MonkeyPatch) -> None:
    http_mock = MagicMock()
    monkeypatch.setattr("urllib.request.urlopen", http_mock)
    investigation_view.investigate_dashboard()
    http_mock.assert_not_called()


def test_crawler_execution_regression(
    investigation_view: InvestigationOperationsView,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    crawl_mock = MagicMock()
    monkeypatch.setattr("pricebrain_app.crawler.adapters.ssg.SSGCrawler.crawl", crawl_mock)
    investigation_view.investigate_dashboard()
    crawl_mock.assert_not_called()


def test_runner_execution_regression(
    investigation_view: InvestigationOperationsView,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_once = MagicMock()
    monkeypatch.setattr(PriceAlertRunner, "run_once", run_once)
    investigation_view.investigate_dashboard()
    run_once.assert_not_called()


def test_notification_dispatch_regression(
    investigation_view: InvestigationOperationsView,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch = MagicMock()
    monkeypatch.setattr(
        "pricebrain_app.crawler.notification_dispatcher.NotificationDispatcher.dispatch",
        dispatch,
    )
    investigation_view.investigate_dashboard()
    dispatch.assert_not_called()


def test_alert_trigger_regression(
    alert_repo: PriceAlertRepository,
    investigation_view: InvestigationOperationsView,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mark_triggered = MagicMock(side_effect=alert_repo.mark_triggered)
    monkeypatch.setattr(alert_repo, "mark_triggered", mark_triggered)
    investigation_view.investigate_dashboard()
    mark_triggered.assert_not_called()


def test_secret_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()
    from pricebrain_app.crawler.logging_utils import redact_secrets

    redacted = redact_secrets(json.dumps({"key": TEST_INGEST_API_KEY}), collect_secrets_for_redaction())
    assert TEST_INGEST_API_KEY not in redacted


def test_json_output(investigation_view: InvestigationOperationsView, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(show_pricebrain_investigation, "build_investigation_operations_view", lambda: investigation_view)
    assert show_pricebrain_investigation.main(["--json"]) == 0


def test_cli_help() -> None:
    with pytest.raises(SystemExit) as exc:
        show_pricebrain_investigation.main(["--help"])
    assert exc.value.code == 0


def test_cli_failures_json(investigation_view: InvestigationOperationsView, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(show_pricebrain_investigation, "build_investigation_operations_view", lambda: investigation_view)
    assert show_pricebrain_investigation.main(["--failures", "--json"]) == 0


def test_cli_area_crawler(investigation_view: InvestigationOperationsView, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(show_pricebrain_investigation, "build_investigation_operations_view", lambda: investigation_view)
    assert show_pricebrain_investigation.main(["--area", "crawler", "--json"]) == 0


def test_cli_area_notification(investigation_view: InvestigationOperationsView, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(show_pricebrain_investigation, "build_investigation_operations_view", lambda: investigation_view)
    assert show_pricebrain_investigation.main(["--area", "notification", "--json"]) == 0


def test_runner_single_failure_warning() -> None:
    findings = analyze_dashboard_snapshot(_snapshot(runner=RunnerDashboardSummary(recent_failed_cycles=1, last_cycle_status="FAILED")))
    assert any(item.code == "RUNNER_CYCLE_FAILED" and item.severity is InvestigationSeverity.WARNING for item in findings)


def test_price_read_error() -> None:
    findings = analyze_dashboard_snapshot(_snapshot(price=PriceDashboardSummary(read_error="price failed")))
    assert any(item.code == "PRICE_READ_ERROR" for item in findings)


def test_alert_no_recent_evaluation() -> None:
    findings = analyze_dashboard_snapshot(
        _snapshot(alerts=AlertDashboardSummary(enabled=2), runner=RunnerDashboardSummary(recent_cycles=0, evaluated=0))
    )
    assert any(item.code == "ALERT_NO_RECENT_EVALUATION" for item in findings)


def test_crawler_http_error_non_ssg() -> None:
    findings = analyze_dashboard_snapshot(
        _snapshot(crawler=CrawlerDashboardSummary(failed_targets=2, ssg_access_denied=1))
    )
    assert any(item.code == "CRAWLER_HTTP_ERROR" for item in findings)


def test_failures_filter_excludes_info() -> None:
    view = InvestigationOperationsView(MagicMock())
    findings_list = [
        InvestigationFinding(
            finding_id="info",
            severity=InvestigationSeverity.INFO,
            area="runner",
            code="RUNNER_HEALTHY",
            title="ok",
            message="ok",
        ),
        InvestigationFinding(
            finding_id="warn",
            severity=InvestigationSeverity.WARNING,
            area="crawler",
            code="CRAWLER_ACCESS_DENIED",
            title="warn",
            message="warn",
        ),
    ]
    view._last_snapshot = DashboardInvestigationSnapshot(
        generated_at=NOW,
        health=DashboardHealthStatus.HEALTHY,
        summary=summarize_findings(findings_list),
        findings=tuple(findings_list),
        dashboard_summary=DashboardSummary(health=DashboardHealthStatus.HEALTHY),
        crawler=CrawlerDashboardSummary(),
        price=PriceDashboardSummary(),
        alerts=AlertDashboardSummary(),
        notifications=NotificationDashboardSummary(),
        runner=RunnerDashboardSummary(last_cycle_status="SUCCESS"),
        audit=AuditDashboardSummary(),
    )
    findings = view.findings(filters=InvestigationFilter(failures_only=True))
    assert all(item.severity is not InvestigationSeverity.INFO for item in findings)


def test_integration_with_runner_cycle(
    investigation_view: InvestigationOperationsView,
    target_repo: CrawlTargetRepository,
    inv_db: FakeFirestoreClient,
    alert_repo: PriceAlertRepository,
) -> None:
    target_repo.merge_catalog(
        mall_id="ssg",
        product_url=PRODUCT_URL,
        product_name="GPU",
        category="gpu",
        tags=["zotac"],
        priority=100,
        now=NOW,
    )
    inv_db.collection(c.LISTINGS).document(LISTING_ID).set(
        {"normalized_product_name": "GPU", "current_price": 1_490_000, "crawled_at": NOW}
    )
    inv_db.collection(c.LISTINGS).document(LISTING_ID).collection(c.PRICE_HISTORY).document("1").set(
        {"price": 1_490_000, "previous_price": 1_599_000, "crawled_at": NOW}
    )
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    service = PriceAlertService(
        alert_repo,
        PriceOperationsView(target_repo, inv_db),
        notification_dispatcher=NotificationDispatcher({NotificationChannel.FAKE: FakeNotificationAdapter()}),
        default_channel=NotificationChannel.FAKE,
        notifications_enabled_override=True,
    )
    PriceAlertRunner(service).run_once(now=NOW)
    snapshot = investigation_view.investigate_dashboard()
    assert snapshot.runner.recent_cycles >= 1
