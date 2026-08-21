"""GPU Master seed data and idempotent seed — docs/05 §3.1–§3.4, docs/09 §6."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from google.cloud.firestore_v1 import Client as FirestoreClient

from pricebrain_app.repository.gpu_repository import GpuRepository

SEED_CREATED_AT = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

GPU_VENDORS: list[dict[str, Any]] = [
    {
        "code": "NVIDIA",
        "name": "NVIDIA",
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
]

GPU_FAMILIES: list[dict[str, Any]] = [
    {
        "code": "GEFORCE_RTX",
        "name": "GeForce RTX",
        "vendor_id": "NVIDIA",
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
]

GPU_MODELS: list[dict[str, Any]] = [
    {
        "slug": "rtx_5080",
        "gpu_series": "RTX",
        "gpu_model": "RTX 5080",
        "vendor_id": "NVIDIA",
        "family_id": "GEFORCE_RTX",
        "vram_gb": 16,
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
]

BOARD_PARTNERS: list[dict[str, Any]] = [
    {
        "slug": "ZOTAC",
        "name": "ZOTAC",
        "display_name": "ZOTAC",
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
]

ALLOWED_SEED_PROJECT_IDS = frozenset({"", "demo-pricebrain"})


def seed_gpu_master(db: FirestoreClient) -> None:
    """Idempotent GPU master seed (merge upsert)."""
    repo = GpuRepository(db)
    repo.seed_vendors(GPU_VENDORS)
    repo.seed_families(GPU_FAMILIES)
    for model in GPU_MODELS:
        slug = str(model["slug"])
        repo.upsert_model(slug, dict(model))
    repo.seed_partners(BOARD_PARTNERS)


def require_emulator_for_seed() -> None:
    """Refuse to seed unless Firestore Emulator is configured."""
    if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
        raise RuntimeError(
            "FIRESTORE_EMULATOR_HOST is required — production GPU master seed is blocked"
        )
    project_id = os.environ.get("FIREBASE_PROJECT_ID", "")
    if project_id not in ALLOWED_SEED_PROJECT_IDS:
        raise RuntimeError(
            f"FIREBASE_PROJECT_ID '{project_id}' is not allowed for GPU master seed"
        )


def count_gpu_master_documents(db: FirestoreClient) -> int:
    repo = GpuRepository(db)
    return (
        len(GPU_VENDORS)
        + len(GPU_FAMILIES)
        + len(GPU_MODELS)
        + len(BOARD_PARTNERS)
    )
