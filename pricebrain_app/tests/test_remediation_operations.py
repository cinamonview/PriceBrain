"""Remediation plan read-only tests."""

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
from pricebrain_app.crawler.dashboard_operations_models import DashboardFilter, DashboardHealthStatus, DashboardSummary
from pricebrain_app.crawler.dashboard_operations_view import DashboardOperationsView
from pricebrain_app.crawler.investigation_operations_models import (
    DashboardInvestigationSnapshot,
    InvestigationFinding,
    InvestigationSeverity,
    InvestigationSummary,
)
from pricebrain_app.crawler.investigation_rules import analyze_dashboard_snapshot
from pricebrain_app.crawler.investigation_operations_view import InvestigationOperationsView
from pricebrain_app.crawler.dashboard_operations_models import (
    AlertDashboardSummary,
    AuditDashboardSummary,
    CrawlerDashboardSummary,
    NotificationDashboardSummary,
    PriceDashboardSummary,
    RunnerDashboardSummary,
)
from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction
from pricebrain_app.crawler.operations_view import CrawlerOperationsView
from pricebrain_app.crawler.price_alert_repository import PriceAlertRepository
from pricebrain_app.crawler.price_alert_runner import PriceAlertRunner
from pricebrain_app.crawler.price_operations_view import PriceOperationsView
from pricebrain_app.crawler.remediation_operations_models import (
    RemediationActionType,
    RemediationFilter,
    RemediationPriority,
    sort_actions,
)
from pricebrain_app.crawler.remediation_operations_view import RemediationOperationsView
from pricebrain_app.crawler.remediation_rules import build_remediation_actions, remediate_finding
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.scripts import show_pricebrain_remediation
from pricebrain_app.tests.conftest import TEST_INGEST_API_KEY
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
TARGET_ID = "ssg_1000832367906"
ALERT_ID = "alert-123"


@pytest.fixture(autouse=True)
def _reset_stores() -> None:
    reset_alert_ops_health_store()
    reset_audit_event_store()


@pytest.fixture
def rem_db() -> FakeFirestoreClient:
    return FakeFirestoreClient()


@pytest.fixture
def remediation_view(rem_db: FakeFirestoreClient) -> RemediationOperationsView:
    target_repo = CrawlTargetRepository(rem_db)
    alert_repo = PriceAlertRepository(rem_db)
    price_view = PriceOperationsView(target_repo, rem_db)
    dashboard_view = DashboardOperationsView(
        CrawlerOperationsView(target_repo, rem_db),
        price_view,
        AlertOperationsView(alert_repo, target_repo, price_view),
        AuditOperationsView(alert_repo),
    )
    return RemediationOperationsView(InvestigationOperationsView(dashboard_view))


def _finding(code: str, **kwargs) -> InvestigationFinding:
    return InvestigationFinding(
        finding_id=kwargs.pop("finding_id", f"finding-{code}"),
        severity=kwargs.pop("severity", InvestigationSeverity.WARNING),
        area=kwargs.pop("area", code.split("_")[0].lower()),
        code=code,
        title=kwargs.pop("title", code),
        message=kwargs.pop("message", code),
        occurred_at=kwargs.pop("occurred_at", NOW),
        **kwargs,
    )


def _snapshot(*findings: InvestigationFinding) -> DashboardInvestigationSnapshot:
    dashboard = PriceBrainDashboardSnapshotHelper(findings)
    return dashboard


class PriceBrainDashboardSnapshotHelper:
    def __init__(self, findings: tuple[InvestigationFinding, ...]) -> None:
        self.findings = findings

    def __call__(self) -> DashboardInvestigationSnapshot:
        return DashboardInvestigationSnapshot(
            generated_at=NOW,
            health=DashboardHealthStatus.DEGRADED,
            summary=InvestigationSummary(
                total_findings=len(self.findings),
                info_count=0,
                warning_count=len(self.findings),
                error_count=0,
                critical_count=0,
                areas=(),
                read_errors=0,
            ),
            findings=self.findings,
            dashboard_summary=DashboardSummary(health=DashboardHealthStatus.DEGRADED),
            crawler=CrawlerDashboardSummary(),
            price=PriceDashboardSummary(),
            alerts=AlertDashboardSummary(),
            notifications=NotificationDashboardSummary(),
            runner=RunnerDashboardSummary(),
            audit=AuditDashboardSummary(),
        )


def _action_for(code: str, **kwargs):
    action, error = remediate_finding(_finding(code, **kwargs))
    assert error is None
    assert action is not None
    return action


def test_a_crawler_access_denied_maps_to_review_ssg_access() -> None:
    action = _action_for("CRAWLER_ACCESS_DENIED", area="crawler")
    assert action.action_type is RemediationActionType.REVIEW_SSG_ACCESS
    assert action.priority is RemediationPriority.HIGH


def test_b_crawler_http_error() -> None:
    action = _action_for("CRAWLER_HTTP_ERROR", area="crawler")
    assert action.action_type is RemediationActionType.REVIEW_CRAWLER_TARGET


def test_c_crawler_no_success() -> None:
    action = _action_for("CRAWLER_NO_SUCCESS", area="crawler")
    assert action.action_type is RemediationActionType.REVIEW_CRAWLER_TARGET


def test_d_price_no_history() -> None:
    action = _action_for("PRICE_NO_HISTORY", area="price")
    assert action.action_type is RemediationActionType.REVIEW_PRICE_HISTORY
    assert action.priority is RemediationPriority.MEDIUM


def test_e_price_read_error() -> None:
    action = _action_for("PRICE_READ_ERROR", area="price")
    assert action.priority is RemediationPriority.HIGH


def test_f_alert_no_recent_evaluation() -> None:
    action = _action_for("ALERT_NO_RECENT_EVALUATION", area="alert")
    assert action.action_type is RemediationActionType.REVIEW_ALERT


def test_g_notification_failure() -> None:
    action = _action_for("NOTIFICATION_FAILURE", area="notification")
    assert action.action_type is RemediationActionType.REVIEW_NOTIFICATION


def test_h_notification_failure_repeated_critical() -> None:
    action = _action_for("NOTIFICATION_FAILURE_REPEATED", area="notification")
    assert action.priority is RemediationPriority.CRITICAL


def test_i_runner_cycle_failed() -> None:
    action = _action_for("RUNNER_CYCLE_FAILED", area="runner")
    assert action.action_type is RemediationActionType.REVIEW_RUNNER


def test_j_runner_cycle_failure_repeated_critical() -> None:
    action = _action_for("RUNNER_CYCLE_FAILURE_REPEATED", area="runner")
    assert action.priority is RemediationPriority.CRITICAL


def test_k_audit_read_error() -> None:
    action = _action_for("AUDIT_READ_ERROR", area="audit")
    assert action.action_type is RemediationActionType.REVIEW_AUDIT


def test_l_runner_healthy_no_action() -> None:
    action = _action_for("RUNNER_HEALTHY", area="runner", severity=InvestigationSeverity.INFO)
    assert action.action_type is RemediationActionType.NO_ACTION


def test_m_unknown_finding_safe_fallback() -> None:
    action = _action_for("UNKNOWN_CODE_XYZ", area="crawler")
    assert action.action_type is RemediationActionType.VERIFY_CONFIGURATION


def test_n_malformed_finding_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    finding = _finding("CRAWLER_HTTP_ERROR", area="crawler")

    def boom(*args, **kwargs):
        raise RuntimeError("malformed finding")

    monkeypatch.setattr(
        "pricebrain_app.crawler.remediation_rules._build_action",
        boom,
    )
    action, error = remediate_finding(finding)
    assert error is not None
    assert action is not None
    assert action.read_error is not None


def _make_plan(actions, *, findings: int = 1) -> "RemediationPlan":
    from pricebrain_app.crawler.remediation_operations_models import RemediationPlan, summarize_actions

    sorted_actions = sort_actions(actions)
    return RemediationPlan(
        generated_at=NOW,
        health=DashboardHealthStatus.DEGRADED,
        total_findings=findings,
        actionable_findings=findings,
        actions=tuple(sorted_actions),
        read_errors=0,
        summary=summarize_actions(sorted_actions),
    )


def test_o_target_filter() -> None:
    snapshot = _snapshot(
        _finding("CRAWLER_ACCESS_DENIED", area="crawler", target_id=TARGET_ID),
        _finding("CRAWLER_ACCESS_DENIED", area="crawler", target_id="other"),
    )()
    actions, _ = build_remediation_actions(snapshot)
    view = RemediationOperationsView(MagicMock())
    view._last_plan = _make_plan(actions, findings=2)
    filtered = view.for_target(TARGET_ID)
    assert all(item.target_id == TARGET_ID for item in filtered)


def test_p_alert_filter() -> None:
    snapshot = _snapshot(
        _finding("NOTIFICATION_FAILURE", area="notification", alert_id=ALERT_ID),
        _finding("NOTIFICATION_FAILURE", area="notification", alert_id="other"),
    )()
    actions, _ = build_remediation_actions(snapshot)
    view = RemediationOperationsView(MagicMock())
    view._last_plan = _make_plan(actions, findings=2)
    filtered = view.for_alert(ALERT_ID)
    assert all(item.alert_id == ALERT_ID for item in filtered)


def test_q_area_filter() -> None:
    snapshot = _snapshot(
        _finding("CRAWLER_ACCESS_DENIED", area="crawler"),
        _finding("PRICE_NO_HISTORY", area="price"),
    )()
    actions, _ = build_remediation_actions(snapshot)
    view = RemediationOperationsView(MagicMock())
    view._last_plan = _make_plan(actions, findings=2)
    filtered = view.by_area("crawler")
    assert all(item.area == "crawler" for item in filtered)


def test_r_priority_filter() -> None:
    snapshot = _snapshot(
        _finding("NOTIFICATION_FAILURE_REPEATED", area="notification"),
        _finding("PRICE_NO_HISTORY", area="price"),
    )()
    actions, _ = build_remediation_actions(snapshot)
    view = RemediationOperationsView(MagicMock())
    view._last_plan = _make_plan(actions, findings=2)
    filtered = view.by_priority("critical")
    assert all(item.priority is RemediationPriority.CRITICAL for item in filtered)


def test_s_sorting() -> None:
    snapshot = _snapshot(
        _finding("PRICE_NO_HISTORY", area="price"),
        _finding("NOTIFICATION_FAILURE_REPEATED", area="notification"),
    )()
    actions, _ = build_remediation_actions(snapshot)
    sorted_actions = sort_actions(actions)
    assert sorted_actions[0].priority is RemediationPriority.CRITICAL


def test_t_json_secret_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()
    from pricebrain_app.crawler.logging_utils import redact_secrets

    redacted = redact_secrets(json.dumps({"key": TEST_INGEST_API_KEY}), collect_secrets_for_redaction())
    assert TEST_INGEST_API_KEY not in redacted


def test_u_read_only_firestore(remediation_view: RemediationOperationsView, rem_db: FakeFirestoreClient) -> None:
    writes = len(rem_db._data)
    remediation_view.build_remediation_plan()
    assert len(rem_db._data) == writes


def test_v_http_guard(remediation_view: RemediationOperationsView, monkeypatch: pytest.MonkeyPatch) -> None:
    http = MagicMock()
    monkeypatch.setattr("urllib.request.urlopen", http)
    remediation_view.build_remediation_plan()
    http.assert_not_called()


def test_w_notification_dispatch_guard(remediation_view: RemediationOperationsView, monkeypatch: pytest.MonkeyPatch) -> None:
    dispatch = MagicMock()
    monkeypatch.setattr(
        "pricebrain_app.crawler.notification_dispatcher.NotificationDispatcher.dispatch",
        dispatch,
    )
    remediation_view.build_remediation_plan()
    dispatch.assert_not_called()


def test_x_runner_execution_guard(remediation_view: RemediationOperationsView, monkeypatch: pytest.MonkeyPatch) -> None:
    run_once = MagicMock()
    monkeypatch.setattr(PriceAlertRunner, "run_once", run_once)
    remediation_view.build_remediation_plan()
    run_once.assert_not_called()


def test_y_crawler_execution_guard(remediation_view: RemediationOperationsView, monkeypatch: pytest.MonkeyPatch) -> None:
    crawl = MagicMock()
    monkeypatch.setattr("pricebrain_app.crawler.adapters.ssg.SSGCrawler.crawl", crawl)
    remediation_view.build_remediation_plan()
    crawl.assert_not_called()


def test_z_human_approval_boundary() -> None:
    codes = [
        "CRAWLER_ACCESS_DENIED",
        "PRICE_NO_HISTORY",
        "NOTIFICATION_FAILURE",
        "RUNNER_HEALTHY",
    ]
    for code in codes:
        action = _action_for(code, area="crawler")
        assert action.human_approval_required is True
        assert action.auto_executable is False


def test_cli_help() -> None:
    with pytest.raises(SystemExit) as exc:
        show_pricebrain_remediation.main(["--help"])
    assert exc.value.code == 0


def test_cli_json(remediation_view: RemediationOperationsView, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(show_pricebrain_remediation, "build_remediation_operations_view", lambda: remediation_view)
    assert show_pricebrain_remediation.main(["--json"]) == 0


def test_cli_failures_json(remediation_view: RemediationOperationsView, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(show_pricebrain_remediation, "build_remediation_operations_view", lambda: remediation_view)
    assert show_pricebrain_remediation.main(["--failures", "--json"]) == 0


def test_build_plan_from_investigation_rules_integration() -> None:
    from pricebrain_app.crawler.dashboard_operations_models import PriceBrainDashboardSnapshot

    dashboard = PriceBrainDashboardSnapshot(
        generated_at=NOW,
        summary=DashboardSummary(health=DashboardHealthStatus.DEGRADED),
        crawler=CrawlerDashboardSummary(ssg_access_denied=2, failed_targets=2, enabled_targets=2),
        price=PriceDashboardSummary(no_history=2, targets=2),
        alerts=AlertDashboardSummary(),
        notifications=NotificationDashboardSummary(),
        runner=RunnerDashboardSummary(),
        audit=AuditDashboardSummary(),
    )
    findings = analyze_dashboard_snapshot(dashboard, generated_at=NOW)
    investigation = DashboardInvestigationSnapshot(
        generated_at=NOW,
        health=DashboardHealthStatus.DEGRADED,
        summary=InvestigationSummary(
            total_findings=len(findings),
            info_count=0,
            warning_count=len(findings),
            error_count=0,
            critical_count=0,
            areas=(),
            read_errors=0,
        ),
        findings=tuple(findings),
        dashboard_summary=dashboard.summary,
        crawler=dashboard.crawler,
        price=dashboard.price,
        alerts=dashboard.alerts,
        notifications=dashboard.notifications,
        runner=dashboard.runner,
        audit=dashboard.audit,
    )
    actions, _ = build_remediation_actions(investigation)
    assert len(actions) >= 2
