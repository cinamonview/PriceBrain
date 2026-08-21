import pytest

from pricebrain_app.firebase.admin import get_firestore_client
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
