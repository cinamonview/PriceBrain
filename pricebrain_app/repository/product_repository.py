"""Product repository — Collection: products (docs/05 §3.5, docs/09 §6)."""

from __future__ import annotations

from typing import Any

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from pricebrain_app.repository import constants as c
from pricebrain_app.repository.base import BaseRepository
from pricebrain_app.repository.identity_snapshot import build_identity_snapshot


def product_payload_from_validated(
    data: dict[str, Any],
    *,
    include_identity_snapshot: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "canonical_product_id": str(data["canonical_product_id"]),
        "brand": data["brand"],
        "board_partner_id": data["board_partner_id"],
        "gpu_model_id": data["gpu_model_id"],
        "normalized_product_name": data["normalized_product_name"],
        "vram_gb": data["vram_gb"],
        "active": True,
    }
    if data.get("manufacturer_part_number") is not None:
        payload["manufacturer_part_number"] = data["manufacturer_part_number"]
    if data.get("image_url"):
        payload["image_url"] = data["image_url"]
    if include_identity_snapshot:
        payload["identity_snapshot"] = build_identity_snapshot(data)
    return payload


class ProductRepository(BaseRepository):
    def upsert_product(self, product_id: str, data: dict[str, Any]) -> str:
        ref = self.db.collection(c.PRODUCTS).document(product_id)
        payload = dict(data)
        payload["updated_at"] = SERVER_TIMESTAMP
        if not ref.get().exists:
            payload.setdefault("active", True)
            payload["created_at"] = SERVER_TIMESTAMP
        ref.set(payload, merge=True)
        return product_id

    def get_by_canonical_id(self, product_id: str) -> dict[str, Any] | None:
        doc = self.db.collection(c.PRODUCTS).document(product_id).get()
        return doc.to_dict() if doc.exists else None

    def upsert_from_validated(self, data: dict[str, Any]) -> str:
        """Direct product upsert — tests only. Application persist must use persist_service."""
        product_id = str(data["canonical_product_id"])
        existing = self.get_by_canonical_id(product_id)
        keep_snapshot = bool(
            existing is not None and isinstance(existing.get("identity_snapshot"), dict)
        )
        payload = product_payload_from_validated(
            data,
            include_identity_snapshot=not keep_snapshot,
        )
        return self.upsert_product(product_id, payload)
