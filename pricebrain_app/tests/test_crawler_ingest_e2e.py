"""TestCrawler and Crawler → Ingest → Firestore E2E (TestClient, no live server)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from pricebrain_app.api.deps import get_firestore
from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.crawler.adapters.ssg import SSGCrawler
from pricebrain_app.crawler.exceptions import IngestClientHTTPError
from pricebrain_app.crawler.models import (
    IngestListingPayload,
    validate_ingest_listing_payload,
)
from pricebrain_app.crawler.test_crawler import TestCrawler
from pricebrain_app.main import app
from pricebrain_app.repository import constants as c
from pricebrain_app.tests.conftest import TEST_INGEST_API_KEY
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient
from pricebrain_app.tests.test_reingest_price_history import (
    LISTING_ID,
    _history_count,
    _latest_history_price,
)


class _TestClientIngestBridge:
    """Same send_listing interface as IngestClient, backed by FastAPI TestClient."""

    def __init__(self, test_client: TestClient, api_key: str) -> None:
        self._client = test_client
        self._api_key = api_key

    def send_listing(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(
            "/internal/ingest/listing",
            json=payload,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        if response.status_code >= 400:
            detail = response.json().get("detail", response.text)
            raise IngestClientHTTPError(
                f"Ingest HTTP {response.status_code}",
                status_code=response.status_code,
                detail=detail,
            )
        return response.json()


@pytest.fixture
def e2e_test_crawler(
    fake_db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> TestCrawler:
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()

    def override_get_firestore():
        yield fake_db

    app.dependency_overrides[get_firestore] = override_get_firestore
    test_client = TestClient(app)
    bridge = _TestClientIngestBridge(test_client, TEST_INGEST_API_KEY)
    yield TestCrawler(ingest_client=bridge)  # type: ignore[arg-type]
    app.dependency_overrides.clear()
    clear_settings_cache()


def test_crawler_builds_standard_payload() -> None:
    crawler = TestCrawler()
    payload = crawler.build_listing_payload(
        price=1_599_000,
        crawled_at=datetime(2026, 8, 21, 11, 0, 0, tzinfo=timezone.utc),
    )
    data = payload.to_dict()
    assert data["product_id"] == "test-rtx5080-001"
    assert data["mall_id"] == "ssg"
    assert data["price"] == 1_599_000
    assert data["crawled_at"] == "2026-08-21T11:00:00+00:00"
    validate_ingest_listing_payload(data)


def test_crawler_payload_requires_positive_integer_price() -> None:
    with pytest.raises(ValueError, match="price must be > 0"):
        IngestListingPayload(
            product_id="test-rtx5080-001",
            product_name="ZOTAC GAMING GeForce RTX 5080 16GB",
            mall_id="ssg",
            product_url="https://example.com/products/test-rtx5080",
            price=0,
            seller="PriceBrain Test",
            crawled_at=datetime(2026, 8, 21, 11, 0, 0, tzinfo=timezone.utc),
        )


def test_crawler_payload_requires_fields() -> None:
    with pytest.raises(ValueError, match="product_id is required"):
        validate_ingest_listing_payload({"price": 1000})


def test_e2e_test_crawler_three_step_price_scenario(
    fake_db: FakeFirestoreClient,
    e2e_test_crawler: TestCrawler,
) -> None:
    results = e2e_test_crawler.run_zotac_price_scenario()

    assert len(results) == 3
    assert results[0]["price_history_appended"] is True
    assert results[1]["price_history_appended"] is False
    assert results[2]["price_history_appended"] is True
    assert results[0]["listing_id"] == LISTING_ID
    assert results[2]["listing_id"] == LISTING_ID

    listing = fake_db.get_document(f"{c.LISTINGS}/{LISTING_ID}")
    assert listing is not None
    assert int(listing["current_price"]) == 1_549_000
    assert _history_count(fake_db, LISTING_ID) == 2
    assert _latest_history_price(fake_db, LISTING_ID) == 1_549_000

    history_prefix = f"{c.LISTINGS}/{LISTING_ID}/{c.PRICE_HISTORY}/"
    history_prices = {
        int(fake_db.get_document(path)["price"])
        for path in fake_db.paths()
        if path.startswith(history_prefix)
    }
    assert history_prices == {1_599_000, 1_549_000}

    product = fake_db.get_document(f"{c.PRODUCTS}/ZOTAC-RTX5080-16GB")
    assert product is not None


def test_e2e_ssg_adapter_fixture_to_mock_ingest(
    fake_db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pathlib import Path

    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()

    def override_get_firestore():
        yield fake_db

    app.dependency_overrides[get_firestore] = override_get_firestore
    test_client = TestClient(app)
    bridge = _TestClientIngestBridge(test_client, TEST_INGEST_API_KEY)

    html = (
        Path(__file__).parent / "fixtures" / "ssg" / "product_gpu.html"
    ).read_text(encoding="utf-8")

    ssg = SSGCrawler()
    payloads = ssg.parse_html(html)
    assert len(payloads) == 1

    try:
        result = bridge.send_listing(payloads[0].to_dict())
        assert result["status"] == "ok"
        assert result["listing_id"] == "SSG_1000832367906"
        assert fake_db.get_document(f"{c.LISTINGS}/SSG_1000832367906") is not None
    finally:
        app.dependency_overrides.clear()
        clear_settings_cache()
