"""Execution history and command center read-only operations tests."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.crawler.alert_ops_health_store import reset_alert_ops_health_store
from pricebrain_app.crawler.audit_event_store import get_audit_event_store, reset_audit_event_store
from pricebrain_app.crawler.command_center_operations_cli import build_command_center_operations_view
from pricebrain_app.crawler.command_center_operations_models import CommandCenterFilter
from pricebrain_app.crawler.execution_health import classify_execution_health
from pricebrain_app.crawler.execution_history_store import (
    get_execution_history_store,
    record_execution_history,
    reset_execution_history_store,
)
from pricebrain_app.crawler.execution_operations_models import (
    ExecutionHealthStatus,
    ExecutionHistoryFilter,
    ExecutionHistoryStatus,
    ExecutionHistorySummary,
)
from pricebrain_app.crawler.execution_operations_view import ExecutionOperationsView
from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction
from pricebrain_app.crawler.remediation_action_handlers import RemediationHandlerContext
from pricebrain_app.crawler.remediation_approval import issue_test_approval_token, reset_remediation_approval_verifier
from pricebrain_app.crawler.remediation_executor import RemediationActionExecutor
from pricebrain_app.crawler.remediation_executor_models import RemediationExecutionMode, RemediationExecutionStatus
from pricebrain_app.crawler.remediation_operations_models import (
    RemediationAction,
    RemediationActionType,
    RemediationPriority,
    RemediationRisk,
)
from pricebrain_app.scripts import show_pricebrain_command_center
from pricebrain_app.tests.conftest import TEST_INGEST_API_KEY
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
TARGET_ID = "ssg_1000832367906"
ALERT_ID = "alert-1"
SECRET_TOKEN = "execution-history-secret-token"


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    reset_alert_ops_health_store()
    reset_audit_event_store()
    reset_remediation_approval_verifier()
    reset_execution_history_store()


@pytest.fixture
def handler_context() -> RemediationHandlerContext:
    db = FakeFirestoreClient()
    from pricebrain_app.crawler.alert_operations_view import AlertOperationsView
    from pricebrain_app.crawler.audit_operations_view import AuditOperationsView
    from pricebrain_app.crawler.operations_view import CrawlerOperationsView
    from pricebrain_app.crawler.price_alert_repository import PriceAlertRepository
    from pricebrain_app.crawler.price_operations_view import PriceOperationsView
    from pricebrain_app.crawler.target_repository import CrawlTargetRepository

    target_repo = CrawlTargetRepository(db)
    alert_repo = PriceAlertRepository(db)
    price_view = PriceOperationsView(target_repo, db)
    return RemediationHandlerContext(
        crawler_view=CrawlerOperationsView(target_repo, db),
        price_view=price_view,
        alert_view=AlertOperationsView(alert_repo, target_repo, price_view),
        audit_view=AuditOperationsView(alert_repo),
    )


@pytest.fixture
def executor(handler_context: RemediationHandlerContext) -> RemediationActionExecutor:
    return RemediationActionExecutor(handler_context)


@pytest.fixture
def execution_view() -> ExecutionOperationsView:
    return ExecutionOperationsView()


def _action(**kwargs) -> RemediationAction:
    return RemediationAction(
        action_id=kwargs.pop("action_id", "action-1"),
        action_type=kwargs.pop("action_type", RemediationActionType.REVIEW_SSG_ACCESS),
        priority=RemediationPriority.HIGH,
        risk=RemediationRisk.HIGH,
        finding_id=kwargs.pop("finding_id", "finding-1"),
        area=kwargs.pop("area", "crawler"),
        title=kwargs.pop("title", "Review SSG access"),
        reason=kwargs.pop("reason", "SSG access denied"),
        recommended_steps=("Review target status",),
        target_id=kwargs.pop("target_id", TARGET_ID),
        alert_id=kwargs.pop("alert_id", None),
        **kwargs,
    )


def _run(executor: RemediationActionExecutor, action: RemediationAction, mode: RemediationExecutionMode, **kwargs):
    return executor.execute(action, mode, now=NOW, **kwargs)


def test_a_plan_history(executor: RemediationActionExecutor, execution_view: ExecutionOperationsView) -> None:
    _run(executor, _action(action_id="plan-action"), RemediationExecutionMode.PLAN)
    entries = execution_view.planned()
    assert entries
    assert entries[0].entry and entries[0].entry.status is ExecutionHistoryStatus.PLANNED


def test_b_dry_run_history(executor: RemediationActionExecutor, execution_view: ExecutionOperationsView) -> None:
    _run(executor, _action(action_id="dry-action"), RemediationExecutionMode.DRY_RUN)
    entries = execution_view.dry_runs()
    assert entries
    assert entries[0].entry and entries[0].entry.status is ExecutionHistoryStatus.DRY_RUN


def test_c_execute_success_history(executor: RemediationActionExecutor, execution_view: ExecutionOperationsView) -> None:
    action = _action(action_id="exec-action")
    token = issue_test_approval_token(action.action_id)
    _run(executor, action, RemediationExecutionMode.EXECUTE, approval_token=token)
    entries = execution_view.executed()
    assert entries
    assert entries[0].entry and entries[0].entry.approval_verified is True


def test_d_blocked_history(executor: RemediationActionExecutor, execution_view: ExecutionOperationsView) -> None:
    _run(executor, _action(action_id="blocked-action"), RemediationExecutionMode.EXECUTE)
    entries = execution_view.blocked()
    assert entries
    assert entries[0].entry and entries[0].entry.status is ExecutionHistoryStatus.BLOCKED


def test_e_failed_history(executor: RemediationActionExecutor, execution_view: ExecutionOperationsView) -> None:
    from pricebrain_app.crawler.remediation_action_handlers import RemediationActionHandler

    class BoomHandler(RemediationActionHandler):
        action_type = RemediationActionType.REVIEW_SSG_ACCESS

        def handle(self, action, context):
            raise RuntimeError("boom")

    executor._handlers = {RemediationActionType.REVIEW_SSG_ACCESS: BoomHandler()}
    _run(executor, _action(action_id="failed-action"), RemediationExecutionMode.DRY_RUN)
    entries = execution_view.failures()
    assert entries
    assert entries[0].entry and entries[0].entry.status is ExecutionHistoryStatus.FAILED


def test_f_action_filter(executor: RemediationActionExecutor, execution_view: ExecutionOperationsView) -> None:
    _run(executor, _action(action_id="filter-action"), RemediationExecutionMode.PLAN)
    _run(executor, _action(action_id="other-action"), RemediationExecutionMode.PLAN)
    entries = execution_view.for_action("filter-action")
    assert len(entries) == 1
    assert entries[0].entry and entries[0].entry.action_id == "filter-action"


def test_g_target_filter(executor: RemediationActionExecutor, execution_view: ExecutionOperationsView) -> None:
    _run(executor, _action(action_id="target-action", target_id=TARGET_ID), RemediationExecutionMode.PLAN)
    entries = execution_view.for_target(TARGET_ID)
    assert entries
    assert entries[0].entry and entries[0].entry.target_id == TARGET_ID


def test_h_alert_filter(executor: RemediationActionExecutor, execution_view: ExecutionOperationsView) -> None:
    _run(
        executor,
        _action(action_id="alert-action", alert_id=ALERT_ID, action_type=RemediationActionType.REVIEW_ALERT, area="alert"),
        RemediationExecutionMode.PLAN,
    )
    entries = execution_view.for_alert(ALERT_ID)
    assert entries
    assert entries[0].entry and entries[0].entry.alert_id == ALERT_ID


def test_i_recent_ordering(
    executor: RemediationActionExecutor,
    execution_view: ExecutionOperationsView,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tick = {"value": NOW}

    def _next_now() -> datetime:
        current = tick["value"]
        tick["value"] = current + timedelta(minutes=1)
        return current

    monkeypatch.setattr("pricebrain_app.crawler.execution_history_store.utc_now", _next_now)
    monkeypatch.setattr("pricebrain_app.crawler.remediation_executor.utc_now", _next_now)
    store = get_execution_history_store()
    store.record_raw(
        {
            "execution_id": "old",
            "action_id": "old-action",
            "action_type": RemediationActionType.REVIEW_SSG_ACCESS.value,
            "mode": "PLAN",
            "status": ExecutionHistoryStatus.PLANNED.value,
            "occurred_at": NOW.isoformat(),
        }
    )
    _run(executor, _action(action_id="new-action"), RemediationExecutionMode.PLAN)
    entries = execution_view.list_recent()
    assert entries[0].entry and entries[0].entry.action_id == "new-action"


def test_j_summary(executor: RemediationActionExecutor, execution_view: ExecutionOperationsView) -> None:
    _run(executor, _action(action_id="sum-plan"), RemediationExecutionMode.PLAN)
    _run(executor, _action(action_id="sum-dry"), RemediationExecutionMode.DRY_RUN)
    summary = execution_view.summarize()
    assert summary.total >= 2
    assert summary.planned >= 1
    assert summary.dry_run >= 1


def test_k_execution_health() -> None:
    health, reasons = classify_execution_health(
        ExecutionHistorySummary(total=3, failed=2, blocked=0, approval_failures=0)
    )
    assert health is ExecutionHealthStatus.CRITICAL
    assert reasons


def test_l_malformed_entry_isolation() -> None:
    store = get_execution_history_store()
    before = store.record_errors
    assert store.record_raw({"bad": "payload"}) is False
    assert store.record_errors == before + 1
    view = ExecutionOperationsView()
    assert view.summarize().read_errors >= 1


def test_m_malformed_audit_isolation() -> None:
    get_audit_event_store().append_raw({"event_type": "INVALID", "broken": True})
    _run(
        RemediationActionExecutor(_handler_context()),
        _action(action_id="audit-isolation"),
        RemediationExecutionMode.PLAN,
    )
    summary = ExecutionOperationsView().summarize()
    assert summary.total >= 1


def _handler_context() -> RemediationHandlerContext:
    db = FakeFirestoreClient()
    from pricebrain_app.crawler.alert_operations_view import AlertOperationsView
    from pricebrain_app.crawler.audit_operations_view import AuditOperationsView
    from pricebrain_app.crawler.operations_view import CrawlerOperationsView
    from pricebrain_app.crawler.price_alert_repository import PriceAlertRepository
    from pricebrain_app.crawler.price_operations_view import PriceOperationsView
    from pricebrain_app.crawler.target_repository import CrawlTargetRepository

    target_repo = CrawlTargetRepository(db)
    alert_repo = PriceAlertRepository(db)
    price_view = PriceOperationsView(target_repo, db)
    return RemediationHandlerContext(
        crawler_view=CrawlerOperationsView(target_repo, db),
        price_view=price_view,
        alert_view=AlertOperationsView(alert_repo, target_repo, price_view),
        audit_view=AuditOperationsView(alert_repo),
    )


def test_n_approval_token_not_stored(executor: RemediationActionExecutor) -> None:
    action = _action(action_id="token-store")
    token = issue_test_approval_token(action.action_id)
    _run(executor, action, RemediationExecutionMode.EXECUTE, approval_token=token)
    raw = get_execution_history_store().list_raw(limit=1)[0]
    assert token not in json.dumps(raw)
    assert "approval_token" not in raw.get("metadata", {})


def test_o_approval_token_not_logged(executor: RemediationActionExecutor, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    action = _action(action_id="token-log")
    token = issue_test_approval_token(action.action_id)
    _run(executor, action, RemediationExecutionMode.EXECUTE, approval_token=token)
    assert token not in caplog.text


def test_p_api_key_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()
    from pricebrain_app.crawler.logging_utils import redact_secrets

    redacted = redact_secrets(json.dumps({"key": TEST_INGEST_API_KEY}), collect_secrets_for_redaction())
    assert TEST_INGEST_API_KEY not in redacted


def test_q_authorization_masking() -> None:
    from pricebrain_app.crawler.logging_utils import redact_secrets

    secret = "Bearer secret-token"
    redacted = redact_secrets(json.dumps({"Authorization": secret}), [secret])
    assert secret not in redacted


def test_r_firestore_write_guard(handler_context: RemediationHandlerContext, executor: RemediationActionExecutor) -> None:
    before = len(handler_context.crawler_view._targets._db._data)
    _run(executor, _action(), RemediationExecutionMode.DRY_RUN)
    assert len(handler_context.crawler_view._targets._db._data) == before


def test_s_http_guard(executor: RemediationActionExecutor, monkeypatch: pytest.MonkeyPatch) -> None:
    http = MagicMock()
    monkeypatch.setattr("urllib.request.urlopen", http)
    _run(executor, _action(), RemediationExecutionMode.DRY_RUN)
    http.assert_not_called()


def test_t_crawler_guard(executor: RemediationActionExecutor, monkeypatch: pytest.MonkeyPatch) -> None:
    crawl = MagicMock()
    monkeypatch.setattr("pricebrain_app.crawler.adapters.ssg.SSGCrawler.crawl", crawl)
    _run(executor, _action(), RemediationExecutionMode.DRY_RUN)
    crawl.assert_not_called()


def test_u_runner_guard(executor: RemediationActionExecutor, monkeypatch: pytest.MonkeyPatch) -> None:
    from pricebrain_app.crawler.price_alert_runner import PriceAlertRunner

    run_once = MagicMock()
    monkeypatch.setattr(PriceAlertRunner, "run_once", run_once)
    action = _action(action_type=RemediationActionType.REVIEW_RUNNER, area="runner")
    _run(executor, action, RemediationExecutionMode.DRY_RUN)
    run_once.assert_not_called()


def test_v_notification_guard(executor: RemediationActionExecutor, monkeypatch: pytest.MonkeyPatch) -> None:
    dispatch = MagicMock()
    monkeypatch.setattr(
        "pricebrain_app.crawler.notification_dispatcher.NotificationDispatcher.dispatch",
        dispatch,
    )
    action = _action(action_type=RemediationActionType.REVIEW_NOTIFICATION, area="notification")
    _run(executor, action, RemediationExecutionMode.DRY_RUN)
    dispatch.assert_not_called()


def test_w_alert_trigger_guard(executor: RemediationActionExecutor, monkeypatch: pytest.MonkeyPatch) -> None:
    mark = MagicMock()
    monkeypatch.setattr(
        "pricebrain_app.crawler.price_alert_repository.PriceAlertRepository.mark_triggered",
        mark,
    )
    action = _action(action_type=RemediationActionType.REVIEW_ALERT, area="alert", alert_id=ALERT_ID)
    _run(executor, action, RemediationExecutionMode.DRY_RUN)
    mark.assert_not_called()


def test_x_command_center_integration() -> None:
    view = build_command_center_operations_view()
    snapshot = view.build_snapshot(filters=CommandCenterFilter(recent=5), now=NOW)
    assert snapshot.dashboard
    assert snapshot.investigation
    assert snapshot.remediation
    assert snapshot.execution
    assert snapshot.health


def test_y_command_center_json() -> None:
    view = build_command_center_operations_view()
    payload = view.build_snapshot(filters=CommandCenterFilter(recent=5), now=NOW).to_dict()
    assert "dashboard" in payload
    assert "execution" in payload
    assert SECRET_TOKEN not in json.dumps(payload)


def test_z_failure_isolation(executor: RemediationActionExecutor, execution_view: ExecutionOperationsView) -> None:
    from pricebrain_app.crawler.remediation_action_handlers import RemediationActionHandler

    class BoomHandler(RemediationActionHandler):
        action_type = RemediationActionType.REVIEW_SSG_ACCESS

        def handle(self, action, context):
            raise RuntimeError("boom")

    executor._handlers = {
        RemediationActionType.REVIEW_SSG_ACCESS: BoomHandler(),
        RemediationActionType.REVIEW_PRICE_HISTORY: executor._handlers[RemediationActionType.REVIEW_PRICE_HISTORY],
    }
    _run(executor, _action(action_id="iso-fail"), RemediationExecutionMode.DRY_RUN)
    _run(
        executor,
        _action(action_id="iso-ok", action_type=RemediationActionType.REVIEW_PRICE_HISTORY, area="price"),
        RemediationExecutionMode.DRY_RUN,
    )
    summary = execution_view.summarize()
    assert summary.failed >= 1
    assert summary.total >= 2


def test_cli_help() -> None:
    with pytest.raises(SystemExit) as exc:
        show_pricebrain_command_center.main(["--help"])
    assert exc.value.code == 0


def test_cli_json_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_view = MagicMock()
    mock_view.build_snapshot.return_value = build_command_center_operations_view().build_snapshot(now=NOW)
    monkeypatch.setattr(show_pricebrain_command_center, "build_command_center_operations_view", lambda: mock_view)
    assert show_pricebrain_command_center.main(["--json"]) == 0
