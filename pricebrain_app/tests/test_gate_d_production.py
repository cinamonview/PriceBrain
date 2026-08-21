"""Gate D — production readiness checks (no production deploy)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pricebrain_app.config.settings import Settings
from pricebrain_app.main import app
from pricebrain_app.repository.gpu_master_seed import require_emulator_for_seed


def test_gate_d_health_is_liveness_only() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "pricebrain_app"


def test_gate_d_production_must_not_use_emulator_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "production-project")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/secrets/sa.json")
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    settings = Settings()
    assert settings.firestore_emulator_host == ""
    assert settings.firebase_configured is True


def test_gate_d_emulator_host_blocks_production_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    with pytest.raises(RuntimeError, match="FIRESTORE_EMULATOR_HOST is required"):
        require_emulator_for_seed()


def test_gate_d_dockerfile_exists_and_uses_port() -> None:
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "requirements-prod.txt" in dockerfile
    assert "0.0.0.0" in dockerfile
    assert "${PORT" in dockerfile or "PORT" in dockerfile
    assert ".env" not in dockerfile
    assert "PRICEBRAIN_INGEST_API_KEY" not in dockerfile


def test_gate_d_dockerignore_excludes_secrets_and_env() -> None:
    root = Path(__file__).resolve().parents[2]
    dockerignore = (root / ".dockerignore").read_text(encoding="utf-8")
    assert ".env" in dockerignore
    assert "serviceAccount" in dockerignore or "serviceAccount*.json" in dockerignore
    assert "pricebrain_app/tests/" in dockerignore


def test_gate_d_no_firestore_in_health_module() -> None:
    health_path = Path(__file__).resolve().parents[1] / "api" / "health.py"
    source = health_path.read_text(encoding="utf-8").lower()
    assert "firebase" not in source
    assert "firestore" not in source
    assert "repository" not in source
    assert "get_firestore" not in source
