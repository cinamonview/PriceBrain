"""Read-only operations API tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from pricebrain_app.api.auth.dependencies import auth_header, viewer_auth_header
from pricebrain_app.api.auth.verifier import FakeTokenVerifier, get_token_verifier, reset_token_verifier
from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.crawler.alert_ops_health_store import reset_alert_ops_health_store
from pricebrain_app.crawler.dashboard_operations_models import CrawlerDashboardSummary
from pricebrain_app.crawler.dashboard_operations_view import DashboardOperationsView
from pricebrain_app.crawler.execution_history_store import get_execution_history_store, reset_execution_history_store
from pricebrain_app.crawler.remediation_approval import issue_test_approval_token, reset_remediation_approval_verifier
from pricebrain_app.crawler.remediation_executor import RemediationActionExecutor
from pricebrain_app.crawler.remediation_executor_models import RemediationExecutionMode
from pricebrain_app.crawler.remediation_operations_models import (
    RemediationAction,
    RemediationActionType,
    RemediationPriority,
    RemediationRisk,
)
from pricebrain_app.main import app
from pricebrain_app.scripts import (
    show_pricebrain_command_center,
    show_pricebrain_dashboard,
    show_pricebrain_investigation,
    show_pricebrain_remediation,
)
from pricebrain_app.tests.conftest import TEST_INGEST_API_KEY

NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
TARGET_ID = "ssg_1000832367906"
ALERT_ID = "alert-1"
SECRET_TOKEN = "operations-api-secret-token"


@pytest.fixture(autouse=True)
def _reset_stores() -> None:
    reset_alert_ops_health_store()
    reset_execution_history_store()
    reset_remediation_approval_verifier()


@pytest.fixture
def operations_client(monkeypatch: pytest.MonkeyPatch, fake_db):
    from pricebrain_app.crawler.price_alert_repository import PriceAlertRepository

    monkeypatch.setenv("PRICEBRAIN_AUTH_ENABLED", "true")
    clear_settings_cache()
    reset_token_verifier()
    fake_verifier = FakeTokenVerifier()
    app.dependency_overrides[get_token_verifier] = lambda: fake_verifier
    monkeypatch.setattr("pricebrain_app.firebase.admin.get_firestore_client", lambda: fake_db)
    monkeypatch.setattr(
        "pricebrain_app.crawler.price_alert_cli.build_price_alert_repository",
        lambda: PriceAlertRepository(fake_db),
    )
    base = TestClient(app)

    class AuthedClient:
        def get(self, url: str, **kwargs):
            headers = dict(kwargs.pop("headers", {}))
            headers.setdefault("Authorization", viewer_auth_header()["Authorization"])
            return base.get(url, headers=headers, **kwargs)

        def post(self, url: str, **kwargs):
            headers = dict(kwargs.pop("headers", {}))
            headers.setdefault("Authorization", viewer_auth_header()["Authorization"])
            return base.post(url, headers=headers, **kwargs)

    client = AuthedClient()
    yield client
    app.dependency_overrides.clear()
    reset_token_verifier()
    clear_settings_cache()


def _seed_execution_history() -> None:
    from pricebrain_app.crawler.remediation_action_handlers import RemediationHandlerContext
    from pricebrain_app.crawler.alert_operations_view import AlertOperationsView
    from pricebrain_app.crawler.audit_operations_view import AuditOperationsView
    from pricebrain_app.crawler.operations_view import CrawlerOperationsView
    from pricebrain_app.crawler.price_alert_repository import PriceAlertRepository
    from pricebrain_app.crawler.price_operations_view import PriceOperationsView
    from pricebrain_app.crawler.target_repository import CrawlTargetRepository
    from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

    db = FakeFirestoreClient()
    target_repo = CrawlTargetRepository(db)
    alert_repo = PriceAlertRepository(db)
    price_view = PriceOperationsView(target_repo, db)
    context = RemediationHandlerContext(
        crawler_view=CrawlerOperationsView(target_repo, db),
        price_view=price_view,
        alert_view=AlertOperationsView(alert_repo, target_repo, price_view),
        audit_view=AuditOperationsView(alert_repo),
    )
    executor = RemediationActionExecutor(context)
    action = RemediationAction(
        action_id="api-action",
        action_type=RemediationActionType.REVIEW_SSG_ACCESS,
        priority=RemediationPriority.HIGH,
        risk=RemediationRisk.HIGH,
        finding_id="finding-1",
        area="crawler",
        title="Review",
        reason="reason",
        recommended_steps=("step",),
        target_id=TARGET_ID,
        alert_id=ALERT_ID,
    )
    executor.execute(action, RemediationExecutionMode.PLAN, now=NOW)
    executor.execute(action, RemediationExecutionMode.EXECUTE, approval_token=None, now=NOW)


# A. Dashboard


def test_dashboard_ok(operations_client: TestClient) -> None:
    response = operations_client.get("/api/operations/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert "summary" in body
    assert "crawler" in body


def test_dashboard_query_filter(operations_client: TestClient) -> None:
    response = operations_client.get("/api/operations/dashboard?category=gpu&recent=5")
    assert response.status_code == 200
    assert response.json()["summary"]["health"] in {"HEALTHY", "DEGRADED", "CRITICAL", "UNKNOWN"}


def test_dashboard_degraded_response(operations_client: TestClient) -> None:
    response = operations_client.get("/api/operations/dashboard")
    assert response.status_code == 200
    assert response.json()["summary"]["health"] in {"HEALTHY", "DEGRADED", "CRITICAL", "UNKNOWN"}


def test_dashboard_section_read_error_isolation(monkeypatch: pytest.MonkeyPatch, operations_client: TestClient) -> None:
    def broken_crawler(self, flt, *, now):
        return CrawlerDashboardSummary(read_error="crawler read failed")

    monkeypatch.setattr(DashboardOperationsView, "_build_crawler", broken_crawler)
    response = operations_client.get("/api/operations/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["crawler"]["read_error"] == "crawler read failed"
    assert "price" in body


# B. Investigation


def test_investigation_findings(operations_client: TestClient) -> None:
    response = operations_client.get("/api/operations/investigation")
    assert response.status_code == 200
    body = response.json()
    assert "findings" in body
    assert "summary" in body


def test_investigation_failures_filter(operations_client: TestClient) -> None:
    response = operations_client.get("/api/operations/investigation?failures=true")
    assert response.status_code == 200
    for item in response.json()["findings"]:
        assert item["severity"] != "INFO"


def test_investigation_area_filter(operations_client: TestClient) -> None:
    response = operations_client.get("/api/operations/investigation?area=crawler")
    assert response.status_code == 200
    for item in response.json()["findings"]:
        assert item["area"] == "crawler"


def test_investigation_target_filter(operations_client: TestClient) -> None:
    response = operations_client.get(f"/api/operations/investigation?target_id={TARGET_ID}")
    assert response.status_code == 200
    for item in response.json()["findings"]:
        assert item.get("target_id") == TARGET_ID


def test_investigation_alert_filter(operations_client: TestClient) -> None:
    response = operations_client.get(f"/api/operations/investigation?alert_id={ALERT_ID}")
    assert response.status_code == 200
    assert isinstance(response.json()["findings"], list)


# C. Remediation


def test_remediation_plan(operations_client: TestClient) -> None:
    response = operations_client.get("/api/operations/remediation")
    assert response.status_code == 200
    body = response.json()
    assert "actions" in body
    assert "summary" in body


def test_remediation_priority_filter(operations_client: TestClient) -> None:
    response = operations_client.get("/api/operations/remediation?priority=high")
    assert response.status_code == 200
    for item in response.json()["actions"]:
        assert item["priority"] == "HIGH"


def test_remediation_area_filter(operations_client: TestClient) -> None:
    response = operations_client.get("/api/operations/remediation?area=crawler")
    assert response.status_code == 200
    for item in response.json()["actions"]:
        assert item["area"] == "crawler"


def test_remediation_target_filter(operations_client: TestClient) -> None:
    response = operations_client.get(f"/api/operations/remediation?target_id={TARGET_ID}")
    assert response.status_code == 200
    for item in response.json()["actions"]:
        assert item.get("target_id") == TARGET_ID


def test_remediation_human_approval_required(operations_client: TestClient) -> None:
    response = operations_client.get("/api/operations/remediation")
    assert response.status_code == 200
    for item in response.json()["actions"]:
        if item["action_type"] != "NO_ACTION":
            assert item["human_approval_required"] is True
            assert item["auto_executable"] is False


# D. Execution


def test_execution_history(operations_client: TestClient) -> None:
    _seed_execution_history()
    response = operations_client.get("/api/operations/execution")
    assert response.status_code == 200
    body = response.json()
    assert "entries" in body
    assert body["summary"]["total"] >= 1


def test_execution_status_filter(operations_client: TestClient) -> None:
    _seed_execution_history()
    response = operations_client.get("/api/operations/execution?status=BLOCKED")
    assert response.status_code == 200
    for item in response.json()["entries"]:
        assert item["entry"]["status"] == "BLOCKED"


def test_execution_blocked_filter(operations_client: TestClient) -> None:
    _seed_execution_history()
    response = operations_client.get("/api/operations/execution?blocked=true")
    assert response.status_code == 200
    for item in response.json()["entries"]:
        assert item["entry"]["status"] == "BLOCKED"


def test_execution_target_action_alert_filters(operations_client: TestClient) -> None:
    _seed_execution_history()
    assert operations_client.get(f"/api/operations/execution?target_id={TARGET_ID}").status_code == 200
    assert operations_client.get("/api/operations/execution?action_id=api-action").status_code == 200
    assert operations_client.get(f"/api/operations/execution?alert_id={ALERT_ID}").status_code == 200


def test_execution_malformed_history_isolation(operations_client: TestClient) -> None:
    get_execution_history_store().record_raw({"broken": True})
    response = operations_client.get("/api/operations/execution")
    assert response.status_code == 200
    assert response.json()["summary"]["read_errors"] >= 1


# E. Command Center


def test_command_center_snapshot(operations_client: TestClient) -> None:
    response = operations_client.get("/api/operations/command-center")
    assert response.status_code == 200
    body = response.json()
    assert "dashboard" in body
    assert "investigation" in body
    assert "remediation" in body
    assert "execution" in body
    assert "health" in body


def test_command_center_failures_filter(operations_client: TestClient) -> None:
    assert operations_client.get("/api/operations/command-center?failures=true").status_code == 200


def test_command_center_blocked_filter(operations_client: TestClient) -> None:
    assert operations_client.get("/api/operations/command-center?blocked=true").status_code == 200


def test_command_center_recent_filter(operations_client: TestClient) -> None:
    assert operations_client.get("/api/operations/command-center?recent=5").status_code == 200


def test_command_center_health_classification(operations_client: TestClient) -> None:
    body = operations_client.get("/api/operations/command-center").json()
    assert body["health"]["dashboard"] in {"HEALTHY", "DEGRADED", "CRITICAL", "UNKNOWN"}
    assert body["health"]["execution"] in {"HEALTHY", "DEGRADED", "CRITICAL", "UNKNOWN"}


# F. Security


def test_api_key_masking(operations_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()
    response = operations_client.get("/api/operations/dashboard")
    assert response.status_code == 200
    assert TEST_INGEST_API_KEY not in response.text


def test_authorization_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    from pricebrain_app.api.operations.models import redact_payload

    secret = "Bearer secret-token"
    payload = redact_payload({"Authorization": secret})
    assert secret not in json.dumps(payload)


def test_approval_token_masking(operations_client: TestClient) -> None:
    token = issue_test_approval_token("api-action")
    _seed_execution_history()
    response = operations_client.get("/api/operations/execution")
    assert response.status_code == 200
    assert token not in response.text
    assert "approval_token" not in response.text


def test_credential_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/secrets/fake.json")
    clear_settings_cache()
    from pricebrain_app.api.operations.models import redact_payload

    payload = redact_payload({"path": "/secrets/fake.json"})
    assert "/secrets/fake.json" not in json.dumps(payload)


# G. Read-only


def test_read_only_guards(operations_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    write = MagicMock()
    http = MagicMock()
    crawl = MagicMock()
    run_once = MagicMock()
    dispatch = MagicMock()
    mark = MagicMock()
    execute = MagicMock()

    monkeypatch.setattr("pricebrain_app.tests.fake_firestore.FakeDocumentReference.set", write)
    monkeypatch.setattr("urllib.request.urlopen", http)
    monkeypatch.setattr("pricebrain_app.crawler.adapters.ssg.SSGCrawler.crawl", crawl)
    from pricebrain_app.crawler.price_alert_runner import PriceAlertRunner

    monkeypatch.setattr(PriceAlertRunner, "run_once", run_once)
    monkeypatch.setattr(
        "pricebrain_app.crawler.notification_dispatcher.NotificationDispatcher.dispatch",
        dispatch,
    )
    monkeypatch.setattr(
        "pricebrain_app.crawler.price_alert_repository.PriceAlertRepository.mark_triggered",
        mark,
    )
    monkeypatch.setattr(RemediationActionExecutor, "execute", execute)

    endpoints = [
        "/api/operations/dashboard",
        "/api/operations/investigation",
        "/api/operations/remediation",
        "/api/operations/execution",
        "/api/operations/command-center",
    ]
    for path in endpoints:
        assert operations_client.get(path).status_code == 200

    write.assert_not_called()
    http.assert_not_called()
    crawl.assert_not_called()
    run_once.assert_not_called()
    dispatch.assert_not_called()
    mark.assert_not_called()
    execute.assert_not_called()


# CLI regression


def test_cli_dashboard_json(monkeypatch: pytest.MonkeyPatch, fake_db) -> None:
    _patch_firestore(monkeypatch, fake_db)
    assert show_pricebrain_dashboard.main(["--json"]) == 0


def test_cli_investigation_json(monkeypatch: pytest.MonkeyPatch, fake_db) -> None:
    _patch_firestore(monkeypatch, fake_db)
    assert show_pricebrain_investigation.main(["--json"]) == 0


def test_cli_remediation_json(monkeypatch: pytest.MonkeyPatch, fake_db) -> None:
    _patch_firestore(monkeypatch, fake_db)
    assert show_pricebrain_remediation.main(["--json"]) == 0


def test_cli_command_center_json(monkeypatch: pytest.MonkeyPatch, fake_db) -> None:
    _patch_firestore(monkeypatch, fake_db)
    assert show_pricebrain_command_center.main(["--json"]) == 0


def _patch_firestore(monkeypatch: pytest.MonkeyPatch, fake_db) -> None:
    from pricebrain_app.crawler.price_alert_repository import PriceAlertRepository

    monkeypatch.setattr("pricebrain_app.firebase.admin.get_firestore_client", lambda: fake_db)
    monkeypatch.setattr(
        "pricebrain_app.crawler.price_alert_cli.build_price_alert_repository",
        lambda: PriceAlertRepository(fake_db),
    )


def test_no_post_execute_routes(operations_client: TestClient) -> None:
    for path in (
        "/api/operations/remediation/execute",
        "/api/operations/alerts/trigger",
        "/api/operations/notifications/send",
        "/api/operations/runner/start",
        "/api/operations/crawler/run",
    ):
        response = operations_client.post(path)
        assert response.status_code == 404
