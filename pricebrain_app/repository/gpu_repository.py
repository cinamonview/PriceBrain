"""GPU catalog repository — docs/09 §6, docs/05 §3.1–§3.4."""

from __future__ import annotations

from typing import Any

from pricebrain_app.repository import constants as c
from pricebrain_app.repository.base import BaseRepository


class GpuRepository(BaseRepository):
    def seed_vendors(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            doc_id = item["code"]
            self.db.collection(c.GPU_VENDORS).document(doc_id).set(item, merge=True)

    def seed_families(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            doc_id = item["code"]
            self.db.collection(c.GPU_FAMILIES).document(doc_id).set(item, merge=True)

    def upsert_model(self, slug: str, data: dict[str, Any]) -> str:
        self.db.collection(c.GPU_MODELS).document(slug).set(data, merge=True)
        return slug

    def seed_partners(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            doc_id = item["slug"]
            self.db.collection(c.BOARD_PARTNERS).document(doc_id).set(item, merge=True)

    def get_vendor(self, code: str) -> dict[str, Any] | None:
        doc = self.db.collection(c.GPU_VENDORS).document(code).get()
        return doc.to_dict() if doc.exists else None

    def get_family(self, code: str) -> dict[str, Any] | None:
        doc = self.db.collection(c.GPU_FAMILIES).document(code).get()
        return doc.to_dict() if doc.exists else None

    def get_model(self, slug: str) -> dict[str, Any] | None:
        doc = self.db.collection(c.GPU_MODELS).document(slug).get()
        return doc.to_dict() if doc.exists else None

    def get_partner(self, slug: str) -> dict[str, Any] | None:
        doc = self.db.collection(c.BOARD_PARTNERS).document(slug).get()
        return doc.to_dict() if doc.exists else None
