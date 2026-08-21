"""Operations API authentication and authorization tests."""

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
from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.crawler.alert_ops_health_store import reset_alert_ops_health_store
from pricebrain_app.crawler.execution_history_store import reset_execution_history_store
from pricebrain_app.crawler.remediation_approval import reset_remediation_approval_verifier
from pricebrain_app.crawler.remediation_executor import RemediationActionExecutor
from pricebrain_app.main import app
from pricebrain_app.scripts import (
    show_pricebrain_command_center,
    show_pricebrain_dashboard,
    show_pricebrain_investigation,
    show_pricebrain_remediation,
)
from pricebrain_app.tests.conftest import TEST_INGEST_API_KEY

ENDPOINTS = [
    "/api/operations/dashboard",
    "/api/operations/investigation",
    "/api/operations/remediation",
    "/api/operations/execution",
    "/api/operations/command-center",
]


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    reset_alert_ops_health_store()
    reset_execution_history_store()
    reset_remediation_approval_verifier()


@pytest.fixture
def auth_client(monkeypatch: pytest.MonkeyPatch, fake_db) -> TestClient:
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


# Authentication


def test_a_missing_token_401(auth_client: TestClient) -> None:
    response = auth_client.get("/api/operations/dashboard")
    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_b_invalid_token_401(auth_client: TestClient) -> None:
    response = auth_client.get("/api/operations/dashboard", headers=auth_header(TEST_INVALID_TOKEN))
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication token"
    assert TEST_INVALID_TOKEN not in response.text


def test_c_malformed_token_401(auth_client: TestClient) -> None:
    response = auth_client.get("/api/operations/dashboard", headers={"Authorization": "Bearer   "})
    assert response.status_code == 401


def test_d_expired_token_401(auth_client: TestClient) -> None:
    response = auth_client.get("/api/operations/dashboard", headers=auth_header(TEST_EXPIRED_TOKEN))
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()
    assert TEST_EXPIRED_TOKEN not in response.text


def test_e_valid_viewer_200(auth_client: TestClient) -> None:
    response = auth_client.get("/api/operations/dashboard", headers=auth_header(TEST_VIEWER_TOKEN))
    assert response.status_code == 200


def test_f_valid_operator_200(auth_client: TestClient) -> None:
    response = auth_client.get("/api/operations/dashboard", headers=auth_header(TEST_OPERATOR_TOKEN))
    assert response.status_code == 200


def test_g_valid_admin_200(auth_client: TestClient) -> None:
    response = auth_client.get("/api/operations/dashboard", headers=auth_header(TEST_ADMIN_TOKEN))
    assert response.status_code == 200


# Authorization


def test_h_no_role_403(auth_client: TestClient) -> None:
    response = auth_client.get("/api/operations/dashboard", headers=auth_header(TEST_NO_ROLE_TOKEN))
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_i_unknown_role_403(auth_client: TestClient) -> None:
    response = auth_client.get("/api/operations/dashboard", headers=auth_header(TEST_UNKNOWN_ROLE_TOKEN))
    assert response.status_code == 403


@pytest.mark.parametrize("path", ENDPOINTS)
def test_j_viewer_access_all_endpoints(auth_client: TestClient, path: str) -> None:
    response = auth_client.get(path, headers=auth_header(TEST_VIEWER_TOKEN))
    assert response.status_code == 200


@pytest.mark.parametrize("path", ENDPOINTS)
def test_k_operator_access_all_endpoints(auth_client: TestClient, path: str) -> None:
    response = auth_client.get(path, headers=auth_header(TEST_OPERATOR_TOKEN))
    assert response.status_code == 200


@pytest.mark.parametrize("path", ENDPOINTS)
def test_l_admin_access_all_endpoints(auth_client: TestClient, path: str) -> None:
    response = auth_client.get(path, headers=auth_header(TEST_ADMIN_TOKEN))
    assert response.status_code == 200


# Security


def test_o_token_not_in_response(auth_client: TestClient) -> None:
    response = auth_client.get("/api/operations/dashboard", headers=auth_header(TEST_VIEWER_TOKEN))
    assert TEST_VIEWER_TOKEN not in response.text
    assert "approval_token" not in response.text


def test_p_token_not_in_logs(auth_client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    auth_client.get("/api/operations/dashboard", headers=auth_header(TEST_VIEWER_TOKEN))
    assert TEST_VIEWER_TOKEN not in caplog.text


def test_q_authorization_header_not_logged(auth_client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    header = auth_header(TEST_VIEWER_TOKEN)["Authorization"]
    auth_client.get("/api/operations/dashboard", headers=auth_header(TEST_VIEWER_TOKEN))
    assert header not in caplog.text


def test_r_credential_not_exposed(auth_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/secrets/fake-service-account.json")
    clear_settings_cache()
    response = auth_client.get("/api/operations/dashboard", headers=auth_header(TEST_VIEWER_TOKEN))
    assert response.status_code == 200
    assert "/secrets/fake-service-account.json" not in response.text


def test_s_api_key_masking(auth_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()
    response = auth_client.get("/api/operations/dashboard", headers=auth_header(TEST_VIEWER_TOKEN))
    assert TEST_INGEST_API_KEY not in response.text
    from pricebrain_app.api.operations.models import redact_payload

    payload = redact_payload({"key": TEST_INGEST_API_KEY})
    assert TEST_INGEST_API_KEY not in json.dumps(payload)


# Read-only


def test_t_read_only_guards(auth_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
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

    for path in ENDPOINTS:
        response = auth_client.get(path, headers=auth_header(TEST_VIEWER_TOKEN))
        assert response.status_code == 200

    write.assert_not_called()
    http.assert_not_called()
    crawl.assert_not_called()
    run_once.assert_not_called()
    dispatch.assert_not_called()
    mark.assert_not_called()
    execute.assert_not_called()


# Regression


def test_ac_forbidden_post_routes(auth_client: TestClient) -> None:
    for path in (
        "/api/operations/remediation/execute",
        "/api/operations/alerts/trigger",
        "/api/operations/notifications/send",
        "/api/operations/runner/start",
        "/api/operations/crawler/run",
    ):
        response = auth_client.post(path, headers=auth_header(TEST_ADMIN_TOKEN))
        assert response.status_code == 404


def test_ab_cli_smoke(monkeypatch: pytest.MonkeyPatch, fake_db) -> None:
    from pricebrain_app.crawler.price_alert_repository import PriceAlertRepository

    monkeypatch.setattr("pricebrain_app.firebase.admin.get_firestore_client", lambda: fake_db)
    monkeypatch.setattr(
        "pricebrain_app.crawler.price_alert_cli.build_price_alert_repository",
        lambda: PriceAlertRepository(fake_db),
    )
    assert show_pricebrain_dashboard.main(["--json"]) == 0
    assert show_pricebrain_investigation.main(["--json"]) == 0
    assert show_pricebrain_remediation.main(["--json"]) == 0
    assert show_pricebrain_command_center.main(["--json"]) == 0


def test_openapi_bearer_auth(auth_client: TestClient) -> None:
    schema = auth_client.get("/openapi.json").json()
    assert "BearerAuth" in schema["components"]["securitySchemes"]
    dashboard = schema["paths"]["/api/operations/dashboard"]["get"]
    assert {"BearerAuth": []} in dashboard.get("security", [])


def test_auth_failure_does_not_reset_stores(auth_client: TestClient) -> None:
    from pricebrain_app.crawler.execution_history_store import get_execution_history_store
    from pricebrain_app.tests.test_operations_api import _seed_execution_history

    _seed_execution_history()
    before = len(get_execution_history_store().list_raw())
    auth_client.get("/api/operations/dashboard")
    assert len(get_execution_history_store().list_raw()) == before
    response = auth_client.get("/api/operations/execution", headers=auth_header(TEST_VIEWER_TOKEN))
    assert response.status_code == 200
    assert response.json()["summary"]["total"] >= before
