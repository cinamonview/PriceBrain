"""Shared CLI helpers for crawler operations commands."""

from __future__ import annotations

import json
import sys
from typing import Any

from pricebrain_app.config.settings import get_settings
from pricebrain_app.crawler.logging_utils import redact_secrets
from pricebrain_app.crawler.operations_view import CrawlerOperationsView
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.firebase.admin import get_firestore_client


def collect_secrets_for_redaction() -> list[str]:
    settings = get_settings()
    secrets: list[str] = []
    if settings.pricebrain_ingest_api_key:
        secrets.append(settings.pricebrain_ingest_api_key)
    if settings.google_application_credentials:
        secrets.append(settings.google_application_credentials)
    return secrets


def build_operations_view() -> CrawlerOperationsView:
    db = get_firestore_client()
    repo = CrawlTargetRepository(db)
    return CrawlerOperationsView(repo, db)


def print_json(payload: Any, *, secrets: list[str] | None = None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    print(redact_secrets(text, secrets or []))


def print_error(message: str) -> None:
    print(message, file=sys.stderr)
