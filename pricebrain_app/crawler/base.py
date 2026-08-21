"""Mall crawler base — docs/07."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pricebrain_app.crawler.types import RawProductData


class BaseMallCrawler(ABC):
    mall_code: str

    @abstractmethod
    def search(self, keyword: str) -> list[RawProductData]:
        """Search mall and return raw parsed products (07 boundary)."""
