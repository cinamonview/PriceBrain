"""Test crawler — no network crawl; reference BaseCrawler implementation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pricebrain_app.crawler.base import BaseCrawler
from pricebrain_app.crawler.client import IngestClient
from pricebrain_app.crawler.models import IngestListingPayload, utc_now_crawled_at

DEFAULT_PRODUCT_ID = "test-rtx5080-001"
DEFAULT_PRODUCT_NAME = "ZOTAC GAMING GeForce RTX 5080 16GB"
DEFAULT_MALL_ID = "ssg"
DEFAULT_PRODUCT_URL = "https://example.com/products/test-rtx5080"
DEFAULT_SELLER = "PriceBrain Test"


class TestCrawler(BaseCrawler):
    """Generate standard ingest payloads and optionally send via IngestClient."""

    __test__ = False

    mall_id = DEFAULT_MALL_ID

    def __init__(self, ingest_client: IngestClient | None = None) -> None:
        self._client = ingest_client

    def crawl(self) -> list[IngestListingPayload]:
        return [
            self.build_listing_payload(
                price=1_599_000,
                crawled_at=datetime(2026, 8, 21, 11, 0, 0, tzinfo=timezone.utc),
            )
        ]

    def build_listing_payload(
        self,
        *,
        price: int,
        crawled_at: datetime | None = None,
        product_id: str = DEFAULT_PRODUCT_ID,
    ) -> IngestListingPayload:
        return IngestListingPayload(
            product_id=product_id,
            product_name=DEFAULT_PRODUCT_NAME,
            mall_id=DEFAULT_MALL_ID,
            product_url=DEFAULT_PRODUCT_URL,
            price=price,
            seller=DEFAULT_SELLER,
            crawled_at=crawled_at or utc_now_crawled_at(),
        )

    def send_listing(self, payload: IngestListingPayload) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("IngestClient is not configured on TestCrawler")
        return self._client.send_listing(payload.to_dict())

    def run_zotac_price_scenario(
        self,
        *,
        product_id: str = DEFAULT_PRODUCT_ID,
    ) -> list[dict[str, Any]]:
        """Three-step price scenario: first ingest, same price, price change."""
        if self._client is None:
            raise RuntimeError("IngestClient is not configured on TestCrawler")

        steps = (
            (1_599_000, datetime(2026, 8, 21, 11, 0, 0, tzinfo=timezone.utc)),
            (1_599_000, datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)),
            (1_549_000, datetime(2026, 8, 21, 13, 0, 0, tzinfo=timezone.utc)),
        )
        results: list[dict[str, Any]] = []
        for price, crawled_at in steps:
            payload = self.build_listing_payload(
                price=price,
                crawled_at=crawled_at,
                product_id=product_id,
            )
            results.append(self.send_listing(payload))
        return results
