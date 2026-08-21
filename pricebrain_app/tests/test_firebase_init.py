import pytest

from pricebrain_app.firebase.admin import get_firestore_client


def test_get_firestore_client_requires_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FIREBASE_PROJECT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)

    import firebase_admin

    for app in list(firebase_admin._apps.values()):
        firebase_admin.delete_app(app)

    from pricebrain_app.config.settings import get_settings

    get_settings.cache_clear()

    with pytest.raises(ValueError, match="FIREBASE_PROJECT_ID"):
        get_firestore_client()

    get_settings.cache_clear()
