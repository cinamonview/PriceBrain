"""Listing repository — Collection: listings (docs/05 §3.8, docs/09 §6)."""

from __future__ import annotations

from typing import Any

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from pricebrain_app.repository import constants as c
from pricebrain_app.repository.base import BaseRepository


def normalize_mall_code_for_document_id(mall_id: str) -> str:
    """Listing document IDs use the uppercase mall code — docs/05 §2.

    Kept dependency-free so the crawler layer can reuse it without importing
    the pipeline layer.
    """
    return mall_id.strip().upper()


def build_listing_document_id(mall_id: str, external_product_id: str) -> str:
    """Document ID rule: {mall_code}_{external_product_id} — docs/05 §2.

    Accepts either casing for `mall_id` so crawl targets (canonical lowercase)
    and ingest (uppercase mall code) resolve to the same document.
    """
    mall_code = normalize_mall_code_for_document_id(mall_id)
    return f"{mall_code}_{external_product_id}"


def build_price_history_document_id(crawled_at_ms: int) -> str:
    """docs/05 §2 price_history Document ID = crawled_at ms string."""
    return str(crawled_at_ms)


class ListingRepository(BaseRepository):
    def upsert_listing(self, listing_id: str, data: dict[str, Any]) -> str:
        ref = self.db.collection(c.LISTINGS).document(listing_id)
        payload = dict(data)
        payload["updated_at"] = SERVER_TIMESTAMP
        ref.set(payload, merge=True)
        return listing_id

    def get_by_mall_product(
        self, mall_id: str, external_product_id: str
    ) -> dict[str, Any] | None:
        listing_id = build_listing_document_id(mall_id, external_product_id)
        doc = self.db.collection(c.LISTINGS).document(listing_id).get()
        return doc.to_dict() if doc.exists else None

    def upsert_from_validated(
        self,
        data: dict[str, Any],
        canonical_product_id: str,
    ) -> str:
        mall_id = str(data["mall_id"])
        external_product_id = str(data["product_id"])
        listing_id = build_listing_document_id(mall_id, external_product_id)
        payload: dict[str, Any] = {
            "product_id": canonical_product_id,
            "mall_id": mall_id,
            "external_product_id": external_product_id,
            "seller_id": str(data["seller_id"]),
            "raw_product_name": data["raw_product_name"],
            "normalized_product_name": data["normalized_product_name"],
            "current_price": data["price"],
            "product_url": data["product_url"],
            "availability": data.get("availability", True),
            "status": data.get("status", "AVAILABLE"),
        }
        if data.get("image_url"):
            payload["image_url"] = data["image_url"]
        if data.get("crawled_at") is not None:
            payload["crawled_at"] = data["crawled_at"]
        return self.upsert_listing(listing_id, payload)


def listing_payload_from_validated(
    data: dict[str, Any],
    canonical_product_id: str,
) -> tuple[str, dict[str, Any]]:
    mall_id = str(data["mall_id"])
    external_product_id = str(data["product_id"])
    listing_id = build_listing_document_id(mall_id, external_product_id)
    payload: dict[str, Any] = {
        "product_id": canonical_product_id,
        "mall_id": mall_id,
        "external_product_id": external_product_id,
        "seller_id": str(data["seller_id"]),
        "raw_product_name": data["raw_product_name"],
        "normalized_product_name": data["normalized_product_name"],
        "current_price": data["price"],
        "product_url": data["product_url"],
        "availability": data.get("availability", True),
        "status": data.get("status", "AVAILABLE"),
        "updated_at": SERVER_TIMESTAMP,
    }
    if data.get("image_url"):
        payload["image_url"] = data["image_url"]
    if data.get("crawled_at") is not None:
        payload["crawled_at"] = data["crawled_at"]
    return listing_id, payload
