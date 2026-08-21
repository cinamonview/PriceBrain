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
