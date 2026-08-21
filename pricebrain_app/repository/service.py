"""ValidatedProduct persist orchestration — docs/09 §6.2."""

from __future__ import annotations

from typing import Any

from google.cloud.firestore_v1 import Client as FirestoreClient

from pricebrain_app.repository.listing_repository import ListingRepository
from pricebrain_app.repository.price_history_repository import PriceHistoryRepository
from pricebrain_app.repository.product_repository import ProductRepository
from pricebrain_app.repository.reference_repository import ReferenceRepository
from pricebrain_app.repository.validation import validate_for_persist


def save_validated_product(
    db: FirestoreClient,
    data: dict[str, Any],
) -> dict[str, str | bool]:
    """Persist ValidatedProduct via Repository layer (09 only — not 07/08)."""
    validate_for_persist(data)

    reference_repo = ReferenceRepository(db)
    product_repo = ProductRepository(db)
    listing_repo = ListingRepository(db)
    price_history_repo = PriceHistoryRepository(db)

    reference_repo.resolve_all(data)

    canonical_product_id = product_repo.upsert_from_validated(data)
    listing_id = listing_repo.upsert_from_validated(data, canonical_product_id)

    price_history_appended = False
    price = data.get("price")
    crawled_at = data.get("crawled_at")
    if price is not None and crawled_at is not None:
        price_history_appended = price_history_repo.append_if_changed(
            listing_id,
            int(price),
            crawled_at,
        )

    return {
        "product_id": canonical_product_id,
        "listing_id": listing_id,
        "price_history_appended": price_history_appended,
    }
