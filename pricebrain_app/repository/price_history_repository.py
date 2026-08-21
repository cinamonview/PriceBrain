"""Price history repository — docs/05 §3.9, docs/09 §6.3."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from pricebrain_app.repository import constants as c
from pricebrain_app.repository.base import BaseRepository
from pricebrain_app.repository.listing_repository import build_price_history_document_id


def normalize_krw_price(price: Any) -> int:
    """Normalize KRW price to int (Firestore may return float)."""
    return int(price)


class PriceHistoryRepository(BaseRepository):
    def _get_latest_history_price(self, listing_id: str) -> int | None:
        listing_ref = self.db.collection(c.LISTINGS).document(listing_id)
        latest_price: int | None = None
        latest_crawled_at: datetime | None = None

        for snapshot in listing_ref.collection(c.PRICE_HISTORY).stream():
            data = snapshot.to_dict()
            if not data or data.get("price") is None or data.get("crawled_at") is None:
                continue
            crawled_at = data["crawled_at"]
            if latest_crawled_at is None or crawled_at > latest_crawled_at:
                latest_crawled_at = crawled_at
                latest_price = normalize_krw_price(data["price"])

        return latest_price

    def append_if_changed(
        self,
        listing_id: str,
        new_price: int,
        crawled_at: datetime,
    ) -> bool:
        """Append price_history when price changed or no history exists yet."""
        new_price = normalize_krw_price(new_price)
        latest_price = self._get_latest_history_price(listing_id)

        if latest_price is not None and latest_price == new_price:
            return False

        listing_ref = self.db.collection(c.LISTINGS).document(listing_id)
        previous_price = latest_price
        price_change = (
            (new_price - previous_price) if previous_price is not None else None
        )

        history_id = build_price_history_document_id(int(crawled_at.timestamp() * 1000))
        listing_ref.collection(c.PRICE_HISTORY).document(history_id).set(
            {
                "price": new_price,
                "crawled_at": crawled_at,
                "previous_price": previous_price,
                "price_change": price_change,
            }
        )
        listing_ref.set(
            {
                "current_price": new_price,
                "crawled_at": crawled_at,
                "updated_at": SERVER_TIMESTAMP,
            },
            merge=True,
        )
        return True
