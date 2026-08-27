"""Seed GPU master data into Firestore — Gate C-3 / V2 Phase 1 Tier-1."""

from __future__ import annotations

import argparse
import os
import sys

from pricebrain_app.firebase.admin import get_firestore_client
from pricebrain_app.repository.gpu_master_seed import (
    require_emulator_for_seed,
    seed_gpu_master,
    summarize_tier1_seed,
)


def _print_seed_plan() -> None:
    counts = summarize_tier1_seed()
    print("Tier-1 GPU master seed plan (merge upsert, idempotent):")
    for key in ("gpu_vendors", "gpu_families", "gpu_models", "board_partners"):
        print(f"  {key}: {counts[key]}")
    print(f"  total documents: {counts['total']}")
    print("  max writes (cold seed):", counts["total"])
    print("  max writes (warm seed, all exist): 0 (merge no-op reads only)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Tier-1 GPU master catalog")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print seed document counts without writing",
    )
    parser.add_argument(
        "--confirm-production",
        action="store_true",
        help="Allow seed against real Firestore (no emulator)",
    )
    args = parser.parse_args()

    if args.dry_run:
        _print_seed_plan()
        return

    emulator_host = os.environ.get("FIRESTORE_EMULATOR_HOST")
    if emulator_host:
        require_emulator_for_seed()
        target = f"Emulator ({emulator_host})"
    elif args.confirm_production:
        target = "Production Firestore"
    else:
        print(
            "Refusing to seed: set FIRESTORE_EMULATOR_HOST or pass --confirm-production",
            file=sys.stderr,
        )
        sys.exit(1)

    counts = summarize_tier1_seed()
    print(f"Seeding {counts['total']} Tier-1 GPU master documents → {target}")
    db = get_firestore_client()
    seed_gpu_master(db)
    print("GPU master seed completed")


if __name__ == "__main__":
    main()
