"""Firebase configuration helpers — SSOT: docs/09 §4, §5."""

from pricebrain_app.config.settings import Settings, get_settings


def get_firebase_options(settings: Settings | None = None) -> dict[str, str]:
    """Build Firebase Admin initialize_app options from settings."""
    settings = settings or get_settings()
    if not settings.firebase_project_id:
        raise ValueError("FIREBASE_PROJECT_ID is required")
    return {"projectId": settings.firebase_project_id}
