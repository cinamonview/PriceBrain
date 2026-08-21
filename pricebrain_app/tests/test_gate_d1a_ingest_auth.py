"""Gate D+1-A — ingest API key authentication tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pricebrain_app.api.deps import get_firestore
from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.main import app
from pricebrain_app.tests.conftest import TEST_INGEST_API_KEY
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient


@pytest.fixture
def ingest_client(
    fake_db: FakeFirestoreClient,
    ingest_auth_env: dict[str, str],
) -> TestClient:
    def override_get_firestore():
        yield fake_db

    app.dependency_overrides[get_firestore] = override_get_firestore
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_d1a_01_health_without_auth() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_d1a_02_ingest_valid_api_key(
    ingest_client: TestClient,
    ingest_auth_env: dict[str, str],
    sample_raw_product: dict,
) -> None:
    response = ingest_client.post(
        "/internal/ingest/listing",
        json=sample_raw_product,
        headers=ingest_auth_env,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.fixture
def sample_raw_product() -> dict:
    from datetime import datetime, timezone

    return {
        "mall": "SSG",
        "product_id": "1000832367906",
        "product_name": "HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB",
        "price": 2429000,
        "seller": "히트정보",
        "product_url": "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906",
        "image_url": "https://sitem.ssgcdn.com/itemimage/1000832367906.jpg",
        "crawled_at": datetime(2026, 8, 19, 10, 0, 0, tzinfo=timezone.utc).isoformat(),
    }


def test_d1a_03_ingest_missing_authorization(
    ingest_client: TestClient,
    sample_raw_product: dict,
) -> None:
    response = ingest_client.post(
        "/internal/ingest/listing",
        json=sample_raw_product,
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing Authorization header"


def test_d1a_04_ingest_invalid_api_key(
    ingest_client: TestClient,
    ingest_auth_env: dict[str, str],
    sample_raw_product: dict,
) -> None:
    headers = {"Authorization": "Bearer wrong-key"}
    response = ingest_client.post(
        "/internal/ingest/listing",
        json=sample_raw_product,
        headers=headers,
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


def test_d1a_05_ingest_malformed_bearer(
    ingest_client: TestClient,
    sample_raw_product: dict,
) -> None:
    for headers in (
        {"Authorization": "NotBearer token"},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer   "},
    ):
        response = ingest_client.post(
            "/internal/ingest/listing",
            json=sample_raw_product,
            headers=headers,
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid Authorization header"


def test_d1a_06_ingest_invalid_payload_after_auth(
    ingest_client: TestClient,
    ingest_auth_env: dict[str, str],
) -> None:
    response = ingest_client.post(
        "/internal/ingest/listing",
        json={"mall": "SSG"},
        headers=ingest_auth_env,
    )
    assert response.status_code == 422


def test_d1a_07_production_style_rejects_when_api_key_missing(
    fake_db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_raw_product: dict,
) -> None:
    monkeypatch.delenv("PRICEBRAIN_INGEST_API_KEY", raising=False)
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "production-project")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/secrets/sa.json")
    clear_settings_cache()

    def override_get_firestore():
        yield fake_db

    app.dependency_overrides[get_firestore] = override_get_firestore
    try:
        client = TestClient(app)
        response = client.post(
            "/internal/ingest/listing",
            json=sample_raw_product,
            headers={"Authorization": f"Bearer {TEST_INGEST_API_KEY}"},
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "Ingest API is not configured"
    finally:
        app.dependency_overrides.clear()
        clear_settings_cache()


def test_d1a_08_crawler_has_no_auth_dependency_imports() -> None:
    crawler_root = Path(__file__).resolve().parents[1] / "crawler"
    forbidden = ("pricebrain_app.api.deps", "require_ingest_api_key")
    for path in crawler_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in source, f"{path} imports auth dependency"


def test_d1a_09_pipeline_has_no_auth_dependency_imports() -> None:
    pipeline_root = Path(__file__).resolve().parents[1] / "pipeline"
    forbidden = ("pricebrain_app.api.deps", "require_ingest_api_key")
    for path in pipeline_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in source, f"{path} imports auth dependency"


def test_d1a_10_no_hardcoded_ingest_secrets_in_source() -> None:
    root = Path(__file__).resolve().parents[2]
    app_root = root / "pricebrain_app"
    forbidden_patterns = (
        "AIza",
        "BEGIN PRIVATE KEY",
        "private_key",
    )
    for path in app_root.rglob("*.py"):
        if "tests" in path.parts or "node_modules" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            assert pattern not in source, f"{path} contains forbidden secret pattern"

    tests_root = app_root / "tests"
    for path in tests_root.rglob("*.py"):
        if "node_modules" in path.parts or path.name.startswith("test_gate_d1a"):
            continue
        source = path.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            assert pattern not in source, f"{path} contains forbidden secret pattern"


def test_d1a_dockerfile_has_no_api_key_or_env_copy() -> None:
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "PRICEBRAIN_INGEST_API_KEY" not in dockerfile
    assert "COPY .env" not in dockerfile
    assert "serviceAccount" not in dockerfile.lower()
    assert "firebase-adminsdk" not in dockerfile.lower()
