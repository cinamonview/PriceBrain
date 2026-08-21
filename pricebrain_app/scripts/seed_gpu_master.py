"""Seed GPU master data into Firestore Emulator — Gate C-3."""

from __future__ import annotations

from pricebrain_app.firebase.admin import get_firestore_client
from pricebrain_app.repository.gpu_master_seed import (
    require_emulator_for_seed,
    seed_gpu_master,
)


def main() -> None:
    require_emulator_for_seed()
    db = get_firestore_client()
    seed_gpu_master(db)
    print("GPU master seed completed (Emulator)")


if __name__ == "__main__":
    main()
