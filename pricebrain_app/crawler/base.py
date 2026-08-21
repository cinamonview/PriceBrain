"""Mall crawler base — docs/07."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pricebrain_app.crawler.client import IngestClient
from pricebrain_app.crawler.models import IngestListingPayload
from pricebrain_app.crawler.types import RawProductData


class BaseMallCrawler(ABC):
    """07 search crawler — outputs RawProductData (runner / batch path)."""

    mall_code: str

    @abstractmethod
    def search(self, keyword: str) -> list[RawProductData]:
        """Search mall and return raw parsed products (07 boundary)."""


class BaseCrawler(ABC):
    """Ingest adapter crawler — outputs IngestListingPayload (HTTP ingest path)."""

    mall_id: str

    @abstractmethod
    def crawl(self, *args: Any, **kwargs: Any) -> list[IngestListingPayload]:
        """Collect listing payloads for ingest API."""

    def send_payloads(
        self,
        payloads: list[IngestListingPayload],
        client: IngestClient,
    ) -> list[dict[str, Any]]:
        """Send payloads through IngestClient (no Firestore access)."""
        return [client.send_listing(payload.to_dict()) for payload in payloads]
