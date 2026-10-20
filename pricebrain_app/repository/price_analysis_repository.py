"""Read-only reads for price analysis — docs/05 §5 (Product별 전체 listing, 가격 이력)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from google.cloud.firestore_v1.base_query import FieldFilter

from pricebrain_app.analysis.models import PricePoint
from pricebrain_app.analysis.product_analysis import ListingHistory
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.base import BaseRepository
from pricebrain_app.repository.price_history_repository import normalize_krw_price


class PriceAnalysisRepository(BaseRepository):
    def get_product(self, product_id: str) -> dict[str, Any] | None:
        doc = self.db.collection(c.PRODUCTS).document(product_id).get()
        return doc.to_dict() if doc.exists else None

    def list_price_points(self, listing_id: str) -> list[PricePoint]:
        listing_ref = self.db.collection(c.LISTINGS).document(listing_id)
        points: list[PricePoint] = []
        for snapshot in listing_ref.collection(c.PRICE_HISTORY).stream():
            data = snapshot.to_dict() or {}
            price = data.get("price")
            crawled_at = data.get("crawled_at")
            if price is None or not isinstance(crawled_at, datetime):
                continue
            points.append(PricePoint(crawled_at=crawled_at, price=normalize_krw_price(price)))
        points.sort(key=lambda point: point.crawled_at)
        return points

    def list_listing_histories(self, product_id: str) -> list[ListingHistory]:
        query = self.db.collection(c.LISTINGS).where(
            filter=FieldFilter("product_id", "==", product_id)
        )
        return [
            ListingHistory(
                listing_id=snapshot.id,
                data=snapshot.to_dict() or {},
                points=self.list_price_points(snapshot.id),
            )
            for snapshot in query.stream()
        ]
