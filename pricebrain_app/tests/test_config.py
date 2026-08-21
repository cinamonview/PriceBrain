import pytest

from pricebrain_app.config.settings import Settings


def test_settings_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "demo-project")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/fake.json")
    monkeypatch.setenv("AI_API_KEY", "test-key")

    settings = Settings()
    assert settings.firebase_project_id == "demo-project"
    assert settings.google_application_credentials == "/tmp/fake.json"
    assert settings.ai_api_key == "test-key"
    assert settings.firebase_configured is True


def test_settings_emulator_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "demo-project")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "localhost:8080")

    settings = Settings()
    assert settings.firebase_configured is True
