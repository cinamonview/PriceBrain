import pytest

from pricebrain_app.firebase.admin import ensure_firebase_admin_initialized, get_firestore_client
from pricebrain_app.tests.conftest import isolate_firebase_env


def test_get_firestore_client_requires_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolate_firebase_env(monkeypatch)

    import firebase_admin

    for app in list(firebase_admin._apps.values()):
        firebase_admin.delete_app(app)

    with pytest.raises(ValueError, match="FIREBASE_PROJECT_ID"):
        get_firestore_client()

    from pricebrain_app.config.settings import clear_settings_cache

    clear_settings_cache()


def test_ensure_firebase_admin_initialized_is_idempotent_with_emulator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import firebase_admin

    for app in list(firebase_admin._apps.values()):
        firebase_admin.delete_app(app)

    monkeypatch.setenv("FIREBASE_PROJECT_ID", "demo-pricebrain")
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
    from pricebrain_app.config.settings import clear_settings_cache

    clear_settings_cache()

    ensure_firebase_admin_initialized()
    assert firebase_admin._apps
    ensure_firebase_admin_initialized()
    assert len(firebase_admin._apps) == 1

    for app in list(firebase_admin._apps.values()):
        firebase_admin.delete_app(app)
    clear_settings_cache()
