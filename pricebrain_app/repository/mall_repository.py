"""Mall repository stub — docs/09 §6."""

from __future__ import annotations

from typing import Any

from pricebrain_app.repository import constants as c
from pricebrain_app.repository.base import BaseRepository


class MallRepository(BaseRepository):
    def seed_malls(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            doc_id = item["code"]
            self.db.collection(c.MALLS).document(doc_id).set(item, merge=True)
