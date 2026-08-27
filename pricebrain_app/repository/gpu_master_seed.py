"""GPU Master seed data and idempotent seed — docs/05 §3.1–§3.4, docs/09 §6."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from google.cloud.firestore_v1 import Client as FirestoreClient

from pricebrain_app.repository.gpu_repository import GpuRepository

SEED_CREATED_AT = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

TIER1_SENTINEL_PARTNER = "GIGABYTE"
TIER1_SENTINEL_MODEL = "rtx_5070"

GPU_VENDORS: list[dict[str, Any]] = [
    {
        "code": "NVIDIA",
        "name": "NVIDIA",
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
    {
        "code": "AMD",
        "name": "AMD",
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
    {
        "code": "RADEON_RX",
        "name": "Radeon RX",
        "vendor_id": "AMD",
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
]

GPU_MODELS: list[dict[str, Any]] = [
    {
        "slug": "rtx_5060",
        "gpu_series": "RTX",
        "gpu_model": "RTX 5060",
        "vendor_id": "NVIDIA",
        "family_id": "GEFORCE_RTX",
        "vram_gb": 8,
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
    {
        "slug": "rtx_5060_ti",
        "gpu_series": "RTX",
        "gpu_model": "RTX 5060 Ti",
        "vendor_id": "NVIDIA",
        "family_id": "GEFORCE_RTX",
        "vram_gb": 8,
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
    {
        "slug": "rtx_5070",
        "gpu_series": "RTX",
        "gpu_model": "RTX 5070",
        "vendor_id": "NVIDIA",
        "family_id": "GEFORCE_RTX",
        "vram_gb": 12,
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
    {
        "slug": "rtx_5070_ti",
        "gpu_series": "RTX",
        "gpu_model": "RTX 5070 Ti",
        "vendor_id": "NVIDIA",
        "family_id": "GEFORCE_RTX",
        "vram_gb": 16,
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
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
    {
        "slug": "rtx_5090",
        "gpu_series": "RTX",
        "gpu_model": "RTX 5090",
        "vendor_id": "NVIDIA",
        "family_id": "GEFORCE_RTX",
        "vram_gb": 32,
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
    {
        "slug": "rx_9070",
        "gpu_series": "RX",
        "gpu_model": "RX 9070",
        "vendor_id": "AMD",
        "family_id": "RADEON_RX",
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
    {
        "slug": "GIGABYTE",
        "name": "GIGABYTE",
        "display_name": "GIGABYTE",
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
    {
        "slug": "ASUS",
        "name": "ASUS",
        "display_name": "ASUS",
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
    {
        "slug": "MSI",
        "name": "MSI",
        "display_name": "MSI",
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
    {
        "slug": "PALIT",
        "name": "PALIT",
        "display_name": "PALIT",
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
    {
        "slug": "PNY",
        "name": "PNY",
        "display_name": "PNY",
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
    {
        "slug": "GALAX",
        "name": "GALAX",
        "display_name": "GALAX",
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
    {
        "slug": "INNO3D",
        "name": "INNO3D",
        "display_name": "INNO3D",
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
    {
        "slug": "GAINWARD",
        "name": "GAINWARD",
        "display_name": "GAINWARD",
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
    {
        "slug": "ASROCK",
        "name": "ASROCK",
        "display_name": "ASROCK",
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
    {
        "slug": "COLORFUL",
        "name": "COLORFUL",
        "display_name": "COLORFUL",
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
    {
        "slug": "SAPPHIRE",
        "name": "SAPPHIRE",
        "display_name": "SAPPHIRE",
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
    {
        "slug": "XFX",
        "name": "XFX",
        "display_name": "XFX",
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
    {
        "slug": "MANLI",
        "name": "MANLI",
        "display_name": "MANLI",
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
    {
        "slug": "POWERCOLOR",
        "name": "POWERCOLOR",
        "display_name": "PowerColor",
        "active": True,
        "created_at": SEED_CREATED_AT,
    },
]

ALLOWED_SEED_PROJECT_IDS = frozenset({"", "demo-pricebrain", "pricebrain-2fd0f"})


def seed_gpu_master(db: FirestoreClient) -> None:
    """Idempotent GPU master seed (merge upsert)."""
    repo = GpuRepository(db)
    repo.seed_vendors(GPU_VENDORS)
    repo.seed_families(GPU_FAMILIES)
    for model in GPU_MODELS:
        slug = str(model["slug"])
        repo.upsert_model(slug, dict(model))
    repo.seed_partners(BOARD_PARTNERS)


def _tier1_gpu_master_complete(repo: GpuRepository) -> bool:
    return (
        repo.get_partner(TIER1_SENTINEL_PARTNER) is not None
        and repo.get_model(TIER1_SENTINEL_MODEL) is not None
    )


def ensure_gpu_master_seeded(db: FirestoreClient) -> None:
    """Bootstrap GPU master catalog when Tier-1 reference documents are missing.

    Uses GIGABYTE + rtx_5070 as sentinels for Tier-1 completeness.
    Idempotent merge upsert — does not bypass master validation.
    """
    repo = GpuRepository(db)
    if _tier1_gpu_master_complete(repo):
        return
    seed_gpu_master(db)


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


def count_gpu_master_documents() -> int:
    return (
        len(GPU_VENDORS)
        + len(GPU_FAMILIES)
        + len(GPU_MODELS)
        + len(BOARD_PARTNERS)
    )


def summarize_tier1_seed() -> dict[str, int]:
    """Document counts for dry-run / quota planning."""
    return {
        "gpu_vendors": len(GPU_VENDORS),
        "gpu_families": len(GPU_FAMILIES),
        "gpu_models": len(GPU_MODELS),
        "board_partners": len(BOARD_PARTNERS),
        "total": count_gpu_master_documents(),
    }
