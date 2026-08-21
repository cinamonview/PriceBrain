import pytest

from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.crawler.config import clear_crawler_config_cache
from pricebrain_app.repository.gpu_master_seed import seed_gpu_master
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

TEST_INGEST_API_KEY = "test-ingest-api-key"

_ENV_KEYS_FIREBASE = (
    "FIREBASE_PROJECT_ID",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "FIRESTORE_EMULATOR_HOST",
)
_ENV_KEYS_INGEST = ("PRICEBRAIN_INGEST_API_KEY",)
_ENV_KEYS_CRAWLER = (
    "PRICEBRAIN_INGEST_API_URL",
    "PRICEBRAIN_CRAWLER_TIMEOUT_SECONDS",
    "PRICEBRAIN_CRAWLER_MAX_RETRIES",
    "PRICEBRAIN_CRAWLER_REQUEST_INTERVAL_SECONDS",
    "PRICEBRAIN_CRAWLER_WORKER_ENABLED",
    "PRICEBRAIN_CRAWLER_POLL_INTERVAL_SECONDS",
    "PRICEBRAIN_CRAWLER_MAX_TARGETS_PER_CYCLE",
    "PRICEBRAIN_CRAWLER_LEASE_SECONDS",
)


def isolate_env(
    monkeypatch: pytest.MonkeyPatch,
    keys: tuple[str, ...],
    *,
    blank_values: bool = False,
) -> None:
    """Remove and optionally blank env vars so local `.env` cannot affect tests."""
    for key in keys:
        monkeypatch.delenv(key, raising=False)
        if blank_values:
            monkeypatch.setenv(key, "")


def isolate_firebase_env(monkeypatch: pytest.MonkeyPatch) -> None:
    isolate_env(monkeypatch, _ENV_KEYS_FIREBASE, blank_values=True)
    clear_settings_cache()


def isolate_ingest_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    isolate_env(monkeypatch, _ENV_KEYS_INGEST, blank_values=True)
    clear_settings_cache()


def isolate_crawler_env(monkeypatch: pytest.MonkeyPatch) -> None:
    isolate_env(monkeypatch, _ENV_KEYS_CRAWLER, blank_values=False)
    monkeypatch.setenv("PRICEBRAIN_CRAWLER_WORKER_ENABLED", "true")
    monkeypatch.setenv("PRICEBRAIN_CRAWLER_POLL_INTERVAL_SECONDS", "0.01")
    monkeypatch.setenv("PRICEBRAIN_CRAWLER_MAX_TARGETS_PER_CYCLE", "10")
    monkeypatch.setenv("PRICEBRAIN_CRAWLER_LEASE_SECONDS", "300")
    clear_settings_cache()
    clear_crawler_config_cache()


@pytest.fixture
def fake_db() -> FakeFirestoreClient:
    db = FakeFirestoreClient()
    seed_gpu_master(db)
    return db


@pytest.fixture
def ingest_auth_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.delenv("PRICEBRAIN_INGEST_API_KEY", raising=False)
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()
    yield {"Authorization": f"Bearer {TEST_INGEST_API_KEY}"}
    clear_settings_cache()


@pytest.fixture
def blank_firebase_env(monkeypatch: pytest.MonkeyPatch) -> None:
    isolate_firebase_env(monkeypatch)
    yield
    clear_settings_cache()


@pytest.fixture
def blank_ingest_api_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    isolate_ingest_api_key(monkeypatch)
    yield
    clear_settings_cache()


@pytest.fixture
def deterministic_crawler_env(monkeypatch: pytest.MonkeyPatch) -> None:
    isolate_crawler_env(monkeypatch)
    yield
    clear_settings_cache()
    clear_crawler_config_cache()
