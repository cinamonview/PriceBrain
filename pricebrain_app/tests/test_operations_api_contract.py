"""Operations API contract and integration gate tests."""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from pricebrain_app.api.auth.dependencies import auth_header
from pricebrain_app.api.auth.verifier import (
    TEST_ADMIN_TOKEN,
    TEST_EXPIRED_TOKEN,
    TEST_INVALID_TOKEN,
    TEST_NO_ROLE_TOKEN,
    TEST_OPERATOR_TOKEN,
    TEST_UNKNOWN_ROLE_TOKEN,
    TEST_VIEWER_TOKEN,
    FakeTokenVerifier,
    get_token_verifier,
    reset_token_verifier,
)
from pricebrain_app.api.operations.contract import FORBIDDEN_OPERATIONS_METHODS, OPERATIONS_ENDPOINTS
from pricebrain_app.api.operations.dependencies import get_dashboard_operations_view
from pricebrain_app.api.operations.schemas import DashboardResponse
from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.crawler.alert_ops_health_store import reset_alert_ops_health_store
from pricebrain_app.crawler.execution_history_store import reset_execution_history_store
from pricebrain_app.crawler.remediation_approval import reset_remediation_approval_verifier
from pricebrain_app.crawler.remediation_executor import RemediationActionExecutor
from pricebrain_app.main import app
from pricebrain_app.tests.conftest import TEST_INGEST_API_KEY

ROLE_TOKENS = {
    "viewer": TEST_VIEWER_TOKEN,
    "operator": TEST_OPERATOR_TOKEN,
    "admin": TEST_ADMIN_TOKEN,
}


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    reset_alert_ops_health_store()
    reset_execution_history_store()
    reset_remediation_approval_verifier()


@pytest.fixture
def contract_client(monkeypatch: pytest.MonkeyPatch, fake_db) -> TestClient:
    from pricebrain_app.crawler.price_alert_repository import PriceAlertRepository

    monkeypatch.setenv("PRICEBRAIN_AUTH_ENABLED", "true")
    clear_settings_cache()
    reset_token_verifier()
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier()
    monkeypatch.setattr("pricebrain_app.firebase.admin.get_firestore_client", lambda: fake_db)
    monkeypatch.setattr(
        "pricebrain_app.crawler.price_alert_cli.build_price_alert_repository",
        lambda: PriceAlertRepository(fake_db),
    )
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
    reset_token_verifier()
    clear_settings_cache()


# Authentication contract


@pytest.mark.parametrize("path", OPERATIONS_ENDPOINTS)
def test_missing_token_401(contract_client: TestClient, path: str) -> None:
    assert contract_client.get(path).status_code == 401


def test_invalid_token_401(contract_client: TestClient) -> None:
    response = contract_client.get("/api/operations/dashboard", headers=auth_header(TEST_INVALID_TOKEN))
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication token"
    assert TEST_INVALID_TOKEN not in response.text


def test_expired_token_401(contract_client: TestClient) -> None:
    response = contract_client.get("/api/operations/dashboard", headers=auth_header(TEST_EXPIRED_TOKEN))
    assert response.status_code == 401
    assert TEST_EXPIRED_TOKEN not in response.text


def test_malformed_token_401(contract_client: TestClient) -> None:
    assert contract_client.get("/api/operations/dashboard", headers={"Authorization": "Bearer   "}).status_code == 401


@pytest.mark.parametrize("role", ["viewer", "operator", "admin"])
def test_valid_role_dashboard_200(contract_client: TestClient, role: str) -> None:
    response = contract_client.get("/api/operations/dashboard", headers=auth_header(ROLE_TOKENS[role]))
    assert response.status_code == 200
    DashboardResponse.model_validate(response.json())


# Authorization contract


def test_no_role_403(contract_client: TestClient) -> None:
    response = contract_client.get("/api/operations/dashboard", headers=auth_header(TEST_NO_ROLE_TOKEN))
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_unknown_role_403(contract_client: TestClient) -> None:
    response = contract_client.get("/api/operations/dashboard", headers=auth_header(TEST_UNKNOWN_ROLE_TOKEN))
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["viewer", "operator", "admin"])
@pytest.mark.parametrize("path", OPERATIONS_ENDPOINTS)
def test_role_endpoint_matrix_200(contract_client: TestClient, role: str, path: str) -> None:
    response = contract_client.get(path, headers=auth_header(ROLE_TOKENS[role]))
    assert response.status_code == 200


# Response schema contract


@pytest.mark.parametrize(
    "path,required_keys",
    [
        ("/api/operations/dashboard", {"generated_at", "summary", "crawler", "price", "alerts", "runner", "audit"}),
        ("/api/operations/investigation", {"generated_at", "health", "summary", "findings"}),
        ("/api/operations/remediation", {"generated_at", "health", "actions", "summary"}),
        ("/api/operations/execution", {"generated_at", "summary", "health", "entries"}),
        ("/api/operations/audit", {"generated_at", "summary", "health", "events"}),
        ("/api/operations/command-center", {"generated_at", "dashboard", "investigation", "remediation", "execution", "health"}),
    ],
)
def test_response_contract_keys(contract_client: TestClient, path: str, required_keys: set[str]) -> None:
    response = contract_client.get(path, headers=auth_header(TEST_VIEWER_TOKEN))
    assert response.status_code == 200
    assert required_keys.issubset(response.json().keys())


def test_remediation_plan_only_contract(contract_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    execute = MagicMock()
    monkeypatch.setattr(RemediationActionExecutor, "execute", execute)
    response = contract_client.get("/api/operations/remediation", headers=auth_header(TEST_VIEWER_TOKEN))
    assert response.status_code == 200
    body = response.json()
    for action in body["actions"]:
        if action["action_type"] == "NO_ACTION":
            continue
        assert action["human_approval_required"] is True
        assert action["auto_executable"] is False
    execute.assert_not_called()


# OpenAPI contract


def test_openapi_bearer_and_endpoints(contract_client: TestClient) -> None:
    schema = contract_client.get("/openapi.json").json()
    assert "BearerAuth" in schema["components"]["securitySchemes"]
    paths = schema["paths"]
    for endpoint in OPERATIONS_ENDPOINTS:
        assert endpoint in paths
        assert "get" in paths[endpoint]
        assert {"BearerAuth": []} in paths[endpoint]["get"].get("security", [])
        assert "200" in paths[endpoint]["get"].get("responses", {})
        assert "401" in paths[endpoint]["get"].get("responses", {})
        assert "403" in paths[endpoint]["get"].get("responses", {})
        assert "500" in paths[endpoint]["get"].get("responses", "")
        for method in FORBIDDEN_OPERATIONS_METHODS:
            assert method not in paths[endpoint]


def test_openapi_response_schemas_exposed(contract_client: TestClient) -> None:
    schema = contract_client.get("/openapi.json").json()
    dashboard = schema["paths"]["/api/operations/dashboard"]["get"]["responses"]["200"]
    assert "content" in dashboard
    assert "application/json" in dashboard["content"]
    assert "schema" in dashboard["content"]["application/json"]


# Security contract


def test_token_not_in_response(contract_client: TestClient) -> None:
    response = contract_client.get("/api/operations/dashboard", headers=auth_header(TEST_VIEWER_TOKEN))
    assert TEST_VIEWER_TOKEN not in response.text


def test_token_not_in_logs(contract_client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    contract_client.get("/api/operations/dashboard", headers=auth_header(TEST_VIEWER_TOKEN))
    assert TEST_VIEWER_TOKEN not in caplog.text


def test_authorization_header_not_logged(contract_client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    header = auth_header(TEST_VIEWER_TOKEN)["Authorization"]
    contract_client.get("/api/operations/dashboard", headers=auth_header(TEST_VIEWER_TOKEN))
    assert header not in caplog.text


def test_api_key_masking(contract_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()
    response = contract_client.get("/api/operations/dashboard", headers=auth_header(TEST_VIEWER_TOKEN))
    assert TEST_INGEST_API_KEY not in response.text


# Read-only guard


def test_read_only_guard_all_endpoints(contract_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
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

    for path in OPERATIONS_ENDPOINTS:
        assert contract_client.get(path, headers=auth_header(TEST_VIEWER_TOKEN)).status_code == 200

    write.assert_not_called()
    http.assert_not_called()
    crawl.assert_not_called()
    run_once.assert_not_called()
    dispatch.assert_not_called()
    mark.assert_not_called()
    execute.assert_not_called()


# Failure isolation


def test_malformed_view_response_isolation(contract_client: TestClient) -> None:
    broken = MagicMock()
    snapshot = MagicMock()
    snapshot.to_dict.return_value = {"generated_at": "x"}
    broken.build_dashboard_snapshot.return_value = snapshot
    app.dependency_overrides[get_dashboard_operations_view] = lambda: broken
    try:
        response = contract_client.get("/api/operations/dashboard", headers=auth_header(TEST_VIEWER_TOKEN))
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"
        assert "generated_at" not in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_dashboard_operations_view, None)


def test_internal_error_no_stack_trace(contract_client: TestClient) -> None:
    broken = MagicMock()
    broken.build_dashboard_snapshot.side_effect = RuntimeError("secret internal path C:\\repo\\boom")
    app.dependency_overrides[get_dashboard_operations_view] = lambda: broken
    try:
        response = contract_client.get("/api/operations/dashboard", headers=auth_header(TEST_VIEWER_TOKEN))
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"
        assert "C:\\repo" not in response.text
        assert "Traceback" not in response.text
    finally:
        app.dependency_overrides.pop(get_dashboard_operations_view, None)


def test_forbidden_post_routes_absent(contract_client: TestClient) -> None:
    for path in (
        "/api/operations/remediation/execute",
        "/api/operations/alerts/trigger",
        "/api/operations/notifications/send",
        "/api/operations/runner/start",
        "/api/operations/crawler/run",
    ):
        assert contract_client.post(path, headers=auth_header(TEST_ADMIN_TOKEN)).status_code == 404
