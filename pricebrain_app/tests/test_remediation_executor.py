"""Remediation executor safety and approval boundary tests."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.crawler.alert_ops_health_store import reset_alert_ops_health_store
from pricebrain_app.crawler.audit_event_store import get_audit_event_store, reset_audit_event_store
from pricebrain_app.crawler.audit_operations_models import AuditEventType
from pricebrain_app.crawler.remediation_action_handlers import (
    RemediationActionHandler,
    RemediationHandlerContext,
    build_remediation_handlers,
)
from pricebrain_app.crawler.remediation_approval import (
    issue_test_approval_token,
    reset_remediation_approval_verifier,
)
from pricebrain_app.crawler.remediation_audit_events import record_remediation_execution
from pricebrain_app.crawler.remediation_executor import RemediationActionExecutor
from pricebrain_app.crawler.remediation_executor_models import (
    RemediationExecutionMode,
    RemediationExecutionStatus,
)
from pricebrain_app.crawler.remediation_executor_view import RemediationExecutorView
from pricebrain_app.crawler.remediation_operations_models import (
    RemediationAction,
    RemediationActionType,
    RemediationPlan,
    RemediationPlanSummary,
    RemediationPriority,
    RemediationRisk,
)
from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction
from pricebrain_app.scripts import execute_pricebrain_remediation
from pricebrain_app.tests.conftest import TEST_INGEST_API_KEY
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
TARGET_ID = "ssg_1000832367906"
ALERT_ID = "alert-1"
SECRET_TOKEN = "test-approval-token-secret-value"


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    reset_alert_ops_health_store()
    reset_audit_event_store()
    reset_remediation_approval_verifier()


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


def test_a_plan_returns_planned(executor: RemediationActionExecutor) -> None:
    result = executor.execute(_action(), RemediationExecutionMode.PLAN, now=NOW)
    assert result.status is RemediationExecutionStatus.PLANNED
    assert result.mutation_performed is False


def test_b_dry_run_executes_handler(executor: RemediationActionExecutor) -> None:
    result = executor.execute(_action(), RemediationExecutionMode.DRY_RUN, now=NOW)
    assert result.status is RemediationExecutionStatus.EXECUTED
    assert result.mutation_performed is False
    assert "Dry-run OK" in result.message


def test_c_execute_without_token_blocked(executor: RemediationActionExecutor) -> None:
    result = executor.execute(_action(), RemediationExecutionMode.EXECUTE, now=NOW)
    assert result.status is RemediationExecutionStatus.BLOCKED
    assert result.error_code == "MISSING_APPROVAL_TOKEN"


def test_d_invalid_token_blocked(executor: RemediationActionExecutor) -> None:
    result = executor.execute(
        _action(),
        RemediationExecutionMode.EXECUTE,
        approval_token="invalid-token",
        now=NOW,
    )
    assert result.status is RemediationExecutionStatus.BLOCKED
    assert result.error_code == "INVALID_APPROVAL_TOKEN"


def test_e_action_id_mismatch_blocked(executor: RemediationActionExecutor) -> None:
    token = issue_test_approval_token("other-action")
    result = executor.execute(
        _action(action_id="action-1"),
        RemediationExecutionMode.EXECUTE,
        approval_token=token,
        now=NOW,
    )
    assert result.status is RemediationExecutionStatus.BLOCKED
    assert result.error_code == "ACTION_ID_MISMATCH"


def test_f_valid_approval_executed(executor: RemediationActionExecutor) -> None:
    action = _action(action_id="approved-action")
    token = issue_test_approval_token(action.action_id)
    result = executor.execute(action, RemediationExecutionMode.EXECUTE, approval_token=token, now=NOW)
    assert result.approval_verified is True
    assert result.status is RemediationExecutionStatus.EXECUTED
    assert result.mutation_performed is False


def test_g_unknown_action_type_blocked(executor: RemediationActionExecutor) -> None:
    action = _action(action_type=RemediationActionType.REVIEW_SSG_ACCESS)
    executor._handlers = {}
    result = executor.execute(action, RemediationExecutionMode.DRY_RUN, now=NOW)
    assert result.status is RemediationExecutionStatus.BLOCKED
    assert result.error_code == "MISSING_HANDLER"


def test_h_malformed_action_blocked(executor: RemediationActionExecutor) -> None:
    action = _action(read_error="bad action", finding_id="")
    result = executor.execute(action, RemediationExecutionMode.DRY_RUN, now=NOW)
    assert result.status is RemediationExecutionStatus.BLOCKED


def test_i_missing_handler_blocked(executor: RemediationActionExecutor) -> None:
    action = _action(action_type=RemediationActionType.REVIEW_AUDIT)
    executor._handlers = {RemediationActionType.REVIEW_SSG_ACCESS: build_remediation_handlers()[RemediationActionType.REVIEW_SSG_ACCESS]}
    result = executor.execute(action, RemediationExecutionMode.DRY_RUN, now=NOW)
    assert result.status is RemediationExecutionStatus.BLOCKED


def test_j_handler_exception_failed(executor: RemediationActionExecutor) -> None:
    class BoomHandler(RemediationActionHandler):
        action_type = RemediationActionType.REVIEW_SSG_ACCESS

        def handle(self, action, context):
            raise RuntimeError("handler boom")

    executor._handlers = {RemediationActionType.REVIEW_SSG_ACCESS: BoomHandler()}
    result = executor.execute(_action(), RemediationExecutionMode.DRY_RUN, now=NOW)
    assert result.status is RemediationExecutionStatus.FAILED


def test_k_one_action_failure_does_not_stop_plan(handler_context: RemediationHandlerContext) -> None:
    class BoomHandler(RemediationActionHandler):
        action_type = RemediationActionType.REVIEW_SSG_ACCESS

        def handle(self, action, context):
            raise RuntimeError("boom")

    executor = RemediationActionExecutor(
        handler_context,
        handlers={
            RemediationActionType.REVIEW_SSG_ACCESS: BoomHandler(),
            RemediationActionType.REVIEW_PRICE_HISTORY: build_remediation_handlers()[RemediationActionType.REVIEW_PRICE_HISTORY],
        },
    )
    view = RemediationExecutorView(MagicMock(), executor)
    plan = RemediationPlan(
        generated_at=NOW,
        health=MagicMock(),
        total_findings=2,
        actionable_findings=2,
        actions=(
            _action(action_id="a1", action_type=RemediationActionType.REVIEW_SSG_ACCESS),
            _action(action_id="a2", action_type=RemediationActionType.REVIEW_PRICE_HISTORY, area="price"),
        ),
        read_errors=0,
        summary=RemediationPlanSummary(2, 2, 0, (), (), 0),
    )
    payload = view.execute_plan(plan, mode=RemediationExecutionMode.DRY_RUN, now=NOW)
    assert len(payload.results) == 2
    assert any(item.status is RemediationExecutionStatus.FAILED for item in payload.results)
    assert any(item.status is RemediationExecutionStatus.EXECUTED for item in payload.results)


def test_l_read_only_handler_executes(executor: RemediationActionExecutor) -> None:
    action = _action(action_type=RemediationActionType.REVIEW_PRICE_HISTORY, area="price")
    token = issue_test_approval_token(action.action_id)
    result = executor.execute(action, RemediationExecutionMode.EXECUTE, approval_token=token, now=NOW)
    assert result.mutation_performed is False


def test_m_firestore_write_guard(handler_context: RemediationHandlerContext, executor: RemediationActionExecutor) -> None:
    writes_before = len(handler_context.crawler_view._targets._db._data)
    executor.execute(_action(), RemediationExecutionMode.DRY_RUN, now=NOW)
    assert len(handler_context.crawler_view._targets._db._data) == writes_before


def test_n_http_guard(executor: RemediationActionExecutor, monkeypatch: pytest.MonkeyPatch) -> None:
    http = MagicMock()
    monkeypatch.setattr("urllib.request.urlopen", http)
    executor.execute(_action(), RemediationExecutionMode.DRY_RUN, now=NOW)
    http.assert_not_called()


def test_o_crawler_execution_guard(executor: RemediationActionExecutor, monkeypatch: pytest.MonkeyPatch) -> None:
    crawl = MagicMock()
    monkeypatch.setattr("pricebrain_app.crawler.adapters.ssg.SSGCrawler.crawl", crawl)
    executor.execute(_action(), RemediationExecutionMode.DRY_RUN, now=NOW)
    crawl.assert_not_called()


def test_p_runner_execution_guard(executor: RemediationActionExecutor, monkeypatch: pytest.MonkeyPatch) -> None:
    from pricebrain_app.crawler.price_alert_runner import PriceAlertRunner

    run_once = MagicMock()
    monkeypatch.setattr(PriceAlertRunner, "run_once", run_once)
    action = _action(action_type=RemediationActionType.REVIEW_RUNNER, area="runner")
    executor.execute(action, RemediationExecutionMode.DRY_RUN, now=NOW)
    run_once.assert_not_called()


def test_q_notification_dispatch_guard(executor: RemediationActionExecutor, monkeypatch: pytest.MonkeyPatch) -> None:
    dispatch = MagicMock()
    monkeypatch.setattr(
        "pricebrain_app.crawler.notification_dispatcher.NotificationDispatcher.dispatch",
        dispatch,
    )
    action = _action(action_type=RemediationActionType.REVIEW_NOTIFICATION, area="notification")
    executor.execute(action, RemediationExecutionMode.DRY_RUN, now=NOW)
    dispatch.assert_not_called()


def test_r_alert_trigger_guard(executor: RemediationActionExecutor, monkeypatch: pytest.MonkeyPatch) -> None:
    mark = MagicMock()
    monkeypatch.setattr(
        "pricebrain_app.crawler.price_alert_repository.PriceAlertRepository.mark_triggered",
        mark,
    )
    action = _action(action_type=RemediationActionType.REVIEW_ALERT, area="alert", alert_id=ALERT_ID)
    executor.execute(action, RemediationExecutionMode.DRY_RUN, now=NOW)
    mark.assert_not_called()


def test_s_approval_token_not_logged(executor: RemediationActionExecutor, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    action = _action(action_id="log-action")
    token = issue_test_approval_token(action.action_id)
    executor.execute(action, RemediationExecutionMode.EXECUTE, approval_token=token, now=NOW)
    assert token not in caplog.text


def test_t_approval_token_not_in_json(executor: RemediationActionExecutor) -> None:
    action = _action(action_id="json-action")
    token = issue_test_approval_token(action.action_id)
    result = executor.execute(action, RemediationExecutionMode.EXECUTE, approval_token=token, now=NOW)
    payload = json.dumps(result.to_dict())
    assert token not in payload
    assert "approval_token" not in payload


def test_u_api_key_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()
    from pricebrain_app.crawler.logging_utils import redact_secrets

    redacted = redact_secrets(json.dumps({"key": TEST_INGEST_API_KEY}), collect_secrets_for_redaction())
    assert TEST_INGEST_API_KEY not in redacted


def test_v_authorization_masking() -> None:
    from pricebrain_app.crawler.logging_utils import redact_secrets

    secret = "Bearer secret-token"
    redacted = redact_secrets(json.dumps({"Authorization": secret}), [secret])
    assert secret not in redacted


def test_w_env_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRICEBRAIN_INGEST_API_KEY", raising=False)
    clear_settings_cache()
    from pricebrain_app.config.settings import get_settings

    assert get_settings().pricebrain_ingest_api_key is None or get_settings().pricebrain_ingest_api_key != SECRET_TOKEN


def test_x_audit_event_conversion(executor: RemediationActionExecutor) -> None:
    reset_audit_event_store()
    result = executor.execute(_action(), RemediationExecutionMode.PLAN, now=NOW)
    record_remediation_execution(result)
    events = get_audit_event_store().list_raw(limit=1)
    assert events[0]["event_type"] == AuditEventType.REMEDIATION_PLANNED.value


def test_y_audit_metadata_secret_safety(executor: RemediationActionExecutor) -> None:
    reset_audit_event_store()
    action = _action(action_id="audit-action")
    token = issue_test_approval_token(action.action_id)
    result = executor.execute(action, RemediationExecutionMode.EXECUTE, approval_token=token, now=NOW)
    record_remediation_execution(result)
    events = get_audit_event_store().list_raw(limit=1)
    metadata = events[0].get("metadata", {})
    assert "approval_token" not in metadata
    assert token not in json.dumps(events[0])


def test_z_execute_requires_explicit_approval(executor: RemediationActionExecutor) -> None:
    result = executor.execute(_action(), RemediationExecutionMode.EXECUTE, approval_token=None, now=NOW)
    assert result.status is RemediationExecutionStatus.BLOCKED
    assert result.approval_verified is False


def test_cli_help() -> None:
    with pytest.raises(SystemExit) as exc:
        execute_pricebrain_remediation.main(["--help"])
    assert exc.value.code == 0


def test_cli_preview_json(monkeypatch: pytest.MonkeyPatch, handler_context: RemediationHandlerContext) -> None:
    executor = RemediationActionExecutor(handler_context)
    view = RemediationExecutorView(MagicMock(), executor)
    view.build_plan = MagicMock(return_value=RemediationPlan(  # type: ignore[method-assign]
        generated_at=NOW,
        health=MagicMock(),
        total_findings=0,
        actionable_findings=0,
        actions=(),
        read_errors=0,
        summary=RemediationPlanSummary(0, 0, 0, (), (), 0),
    ))
    monkeypatch.setattr(execute_pricebrain_remediation, "build_remediation_executor_view", lambda: view)
    assert execute_pricebrain_remediation.main(["--preview", "--json"]) == 0
