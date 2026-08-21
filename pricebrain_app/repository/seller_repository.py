"""Seller repository stub — docs/09 §6."""

from __future__ import annotations

from typing import Any

from pricebrain_app.repository import constants as c
from pricebrain_app.repository.base import BaseRepository


class SellerRepository(BaseRepository):
    def upsert_seller(self, seller_id: str, data: dict[str, Any]) -> str:
        self.db.collection(c.SELLERS).document(seller_id).set(data, merge=True)
        return seller_id
