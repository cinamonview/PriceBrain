"""BaseCrawler interface tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pricebrain_app.crawler.base import BaseCrawler
from pricebrain_app.crawler.client import IngestClient
from pricebrain_app.crawler.models import IngestListingPayload
from pricebrain_app.crawler.test_crawler import TestCrawler


def test_base_crawler_test_crawler_is_subclass() -> None:
    assert issubclass(TestCrawler, BaseCrawler)
    crawler = TestCrawler()
    assert crawler.mall_id == "ssg"
    payloads = crawler.crawl()
    assert len(payloads) == 1
    assert isinstance(payloads[0], IngestListingPayload)


def test_base_crawler_send_payloads_with_mock_client() -> None:
    sent: list[dict] = []

    class _MockClient:
        def send_listing(self, payload: dict) -> dict:
            sent.append(payload)
            return {"status": "ok"}

    crawler = TestCrawler()
    payload = crawler.build_listing_payload(
        price=1_599_000,
        crawled_at=datetime(2026, 8, 21, 11, 0, 0, tzinfo=timezone.utc),
    )
    results = crawler.send_payloads([payload], _MockClient())  # type: ignore[arg-type]
    assert len(results) == 1
    assert sent[0]["product_id"] == "test-rtx5080-001"


def test_base_crawler_cannot_instantiate_directly() -> None:
    with pytest.raises(TypeError):
        BaseCrawler()  # type: ignore[abstract]
