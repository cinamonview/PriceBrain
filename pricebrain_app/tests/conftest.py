import pytest

from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.repository.gpu_master_seed import seed_gpu_master
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

TEST_INGEST_API_KEY = "test-ingest-api-key"


@pytest.fixture
def fake_db() -> FakeFirestoreClient:
    db = FakeFirestoreClient()
    seed_gpu_master(db)
    return db


@pytest.fixture
def ingest_auth_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()
    yield {"Authorization": f"Bearer {TEST_INGEST_API_KEY}"}
    clear_settings_cache()
