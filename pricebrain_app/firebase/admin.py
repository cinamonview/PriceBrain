"""Firebase Admin SDK initialization — SSOT: docs/09 §5."""

from __future__ import annotations

import os

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import Client as FirestoreClient

from pricebrain_app.config.settings import get_settings
from pricebrain_app.firebase.config import get_firebase_options


def get_firestore_client() -> FirestoreClient:
    """Return a Firestore client via Firebase Admin SDK (server-side only)."""
    if firebase_admin._apps:
        return firestore.client()

    settings = get_settings()
    options = get_firebase_options(settings)

    if settings.firestore_emulator_host:
        os.environ.setdefault(
            "FIRESTORE_EMULATOR_HOST", settings.firestore_emulator_host
        )
        firebase_admin.initialize_app(options=options)
        return firestore.client()

    if not settings.google_application_credentials:
        raise ValueError(
            "GOOGLE_APPLICATION_CREDENTIALS is required when "
            "FIRESTORE_EMULATOR_HOST is not set"
        )

    cred = credentials.Certificate(settings.google_application_credentials)
    firebase_admin.initialize_app(cred, options)
    return firestore.client()
