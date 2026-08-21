"""Application settings — env SSOT: project.mdc §13."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    firebase_project_id: str = Field(default="", alias="FIREBASE_PROJECT_ID")
    google_application_credentials: str = Field(
        default="", alias="GOOGLE_APPLICATION_CREDENTIALS"
    )
    ai_api_key: str = Field(default="", alias="AI_API_KEY")
    firestore_emulator_host: str = Field(default="", alias="FIRESTORE_EMULATOR_HOST")
    pricebrain_ingest_api_key: str = Field(
        default="", alias="PRICEBRAIN_INGEST_API_KEY"
    )
    pricebrain_ingest_api_url: str = Field(
        default="http://127.0.0.1:8000", alias="PRICEBRAIN_INGEST_API_URL"
    )
    pricebrain_test_ssg_url: str = Field(default="", alias="PRICEBRAIN_TEST_SSG_URL")
    pricebrain_crawler_timeout_seconds: float = Field(
        default=15.0, alias="PRICEBRAIN_CRAWLER_TIMEOUT_SECONDS"
    )
    pricebrain_crawler_max_retries: int = Field(
        default=2, alias="PRICEBRAIN_CRAWLER_MAX_RETRIES"
    )
    pricebrain_crawler_backoff_seconds: str = Field(
        default="", alias="PRICEBRAIN_CRAWLER_BACKOFF_SECONDS"
    )
    pricebrain_crawler_request_interval_seconds: float = Field(
        default=0.0, alias="PRICEBRAIN_CRAWLER_REQUEST_INTERVAL_SECONDS"
    )
    pricebrain_crawler_worker_enabled: bool = Field(
        default=True, alias="PRICEBRAIN_CRAWLER_WORKER_ENABLED"
    )
    pricebrain_crawler_poll_interval_seconds: float = Field(
        default=60.0, alias="PRICEBRAIN_CRAWLER_POLL_INTERVAL_SECONDS"
    )
    pricebrain_crawler_max_targets_per_cycle: int = Field(
        default=10, alias="PRICEBRAIN_CRAWLER_MAX_TARGETS_PER_CYCLE"
    )
    pricebrain_crawler_lease_seconds: int = Field(
        default=300, alias="PRICEBRAIN_CRAWLER_LEASE_SECONDS"
    )
    pricebrain_notification_enabled: bool = Field(
        default=False, alias="PRICEBRAIN_NOTIFICATION_ENABLED"
    )
    pricebrain_notification_default_channel: str = Field(
        default="console", alias="PRICEBRAIN_NOTIFICATION_DEFAULT_CHANNEL"
    )

    @property
    def firebase_configured(self) -> bool:
        if self.firestore_emulator_host:
            return bool(self.firebase_project_id)
        return bool(
            self.firebase_project_id and self.google_application_credentials
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
