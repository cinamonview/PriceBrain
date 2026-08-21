"""Firestore Emulator helpers for integration tests."""

from __future__ import annotations

import os
import socket
from collections.abc import Iterator
from contextlib import contextmanager

import firebase_admin
import pytest
from firebase_admin import credentials, initialize_app

EMULATOR_HOST = os.environ.get("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
EMULATOR_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "demo-pricebrain")


def parse_emulator_host(host_value: str) -> tuple[str, int]:
    if ":" in host_value:
        host, port_str = host_value.rsplit(":", 1)
        return host, int(port_str)
    return host_value, 8080


def is_emulator_running(host: str | None = None, port: int | None = None) -> bool:
    host_value = host or parse_emulator_host(EMULATOR_HOST)[0]
    port_value = port or parse_emulator_host(EMULATOR_HOST)[1]
    try:
        with socket.create_connection((host_value, port_value), timeout=1.0):
            return True
    except OSError:
        return False


def reset_firebase_apps() -> None:
    for app in list(firebase_admin._apps.values()):
        firebase_admin.delete_app(app)


def _initialize_emulator_admin_app(project_id: str) -> None:
    """Pre-init Admin SDK for emulator without production ADC (admin.py unchanged)."""
    from google.auth.credentials import AnonymousCredentials

    class _EmulatorAdminCredential(credentials.Base):
        def get_credential(self):
            return AnonymousCredentials()

    reset_firebase_apps()
    initialize_app(_EmulatorAdminCredential(), {"projectId": project_id})


@contextmanager
def emulator_env(
    *,
    host: str = EMULATOR_HOST,
    project_id: str = EMULATOR_PROJECT_ID,
) -> Iterator[None]:
    previous = {
        "FIRESTORE_EMULATOR_HOST": os.environ.get("FIRESTORE_EMULATOR_HOST"),
        "FIREBASE_PROJECT_ID": os.environ.get("FIREBASE_PROJECT_ID"),
        "GOOGLE_APPLICATION_CREDENTIALS": os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
    }
    os.environ["FIRESTORE_EMULATOR_HOST"] = host
    os.environ["FIREBASE_PROJECT_ID"] = project_id
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    reset_firebase_apps()
    from pricebrain_app.config.settings import get_settings

    get_settings.cache_clear()
    _initialize_emulator_admin_app(project_id)
    from pricebrain_app.firebase.admin import get_firestore_client
    from pricebrain_app.repository.gpu_master_seed import seed_gpu_master

    seed_gpu_master(get_firestore_client())
    try:
        yield
    finally:
        reset_firebase_apps()
        get_settings.cache_clear()
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


requires_emulator = pytest.mark.skipif(
    not is_emulator_running(),
    reason="SKIPPED — Firestore Emulator not running (127.0.0.1:8080)",
)
