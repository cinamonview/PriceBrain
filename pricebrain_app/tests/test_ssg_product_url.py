"""SSG single product URL crawl tests — mocked HTTP and fixtures only."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from pricebrain_app.api.deps import get_firestore
from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.crawler.adapters.ssg import SSGCrawler, SSGHtmlFetcher, SSGProductParser
from pricebrain_app.crawler.exceptions import (
    CrawlerHTTPError,
    CrawlerRetryExhaustedError,
    CrawlerTimeoutError,
)
from pricebrain_app.crawler.http_client import HttpClient
from pricebrain_app.crawler.malls.ssg import validate_ssg_product_url
from pricebrain_app.crawler.parser.ssg import parse_ssg_product_page_html
from pricebrain_app.main import app
from pricebrain_app.repository import constants as c
from pricebrain_app.tests.conftest import TEST_INGEST_API_KEY
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient
from pricebrain_app.tests.test_crawler_ingest_e2e import _TestClientIngestBridge
from pricebrain_app.tests.test_repository import _history_count, _latest_history_price

FIXTURES = Path(__file__).parent / "fixtures" / "ssg"
PRODUCT_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _mock_http(handler) -> HttpClient:
    transport = httpx.MockTransport(handler)
    return HttpClient(client=httpx.Client(transport=transport), sleep_func=lambda _: None)


def test_crawl_product_url_fetches_parses_with_mock_http() -> None:
    html = _read_fixture("product_gpu.html")
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, text=html, request=request)

    fetcher = SSGHtmlFetcher(http_client=_mock_http(handler))
    crawler = SSGCrawler(fetcher=fetcher)

    payload = crawler.crawl_product_url(PRODUCT_URL)

    assert requested_urls == [PRODUCT_URL]
    assert payload.product_id == "1000832367906"
    assert payload.price == 2_429_000
    assert payload.mall_id == "ssg"
    assert payload.crawled_at is not None
    crawler.close()


def test_fetch_product_html_raises_on_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found", request=request)

    fetcher = SSGHtmlFetcher(http_client=_mock_http(handler))

    with pytest.raises(CrawlerHTTPError) as exc_info:
        fetcher.fetch_product_html(PRODUCT_URL)
    assert exc_info.value.status_code == 404
    fetcher.close()


def test_fetch_product_html_retries_then_raises_on_500() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(500, text="error", request=request)

    http = HttpClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=2,
        sleep_func=lambda _: None,
    )
    fetcher = SSGHtmlFetcher(http_client=http)

    with pytest.raises(CrawlerRetryExhaustedError):
        fetcher.fetch_product_html(PRODUCT_URL)
    assert attempts["n"] == 3
    fetcher.close()


def test_fetch_product_html_timeout_raises_crawler_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    http = HttpClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0,
        sleep_func=lambda _: None,
    )
    fetcher = SSGHtmlFetcher(http_client=http)

    with pytest.raises(CrawlerTimeoutError):
        fetcher.fetch_product_html(PRODUCT_URL)
    fetcher.close()


def test_product_detail_fixture_parses_to_payload() -> None:
    html = _read_fixture("product_detail_gpu.html")
    crawled_at = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
    raw = parse_ssg_product_page_html(
        html,
        product_url=PRODUCT_URL,
        crawled_at=crawled_at,
    )
    assert raw is not None
    assert raw["product_id"] == "1000832367906"
    assert raw["price"] == 1_599_000
    assert raw["seller"] == "히트정보"
    assert raw["crawled_at"] == crawled_at

    parser = SSGProductParser()
    payload = parser.parse(html, PRODUCT_URL, crawled_at=crawled_at)
    assert payload.price == 1_599_000
    assert payload.crawled_at == crawled_at


def test_validate_ssg_product_url_rejects_non_ssg_host() -> None:
    with pytest.raises(ValueError, match="not an SSG product page"):
        validate_ssg_product_url("https://example.com/item/itemView.ssg?itemId=1")


def test_e2e_ssg_product_url_fixture_to_ingest(
    fake_db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()

    def override_get_firestore():
        yield fake_db

    app.dependency_overrides[get_firestore] = override_get_firestore
    test_client = TestClient(app)
    bridge = _TestClientIngestBridge(test_client, TEST_INGEST_API_KEY)

    html = _read_fixture("product_detail_gpu.html")
    parser = SSGProductParser()
    crawled_at = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
    payload = parser.parse(html, PRODUCT_URL, crawled_at=crawled_at)

    try:
        result = bridge.send_listing(payload.to_dict())
        assert result["status"] == "ok"
        assert result["listing_id"] == "SSG_1000832367906"
        assert fake_db.get_document(f"{c.LISTINGS}/SSG_1000832367906") is not None
    finally:
        app.dependency_overrides.clear()
        clear_settings_cache()


def _detail_html_with_price(price: int) -> str:
    formatted = f"{price:,}"
    return f"""<!DOCTYPE html>
<html><body>
  <h2 class="cdtl_info_tit">HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB</h2>
  <span class="cdtl_info_tit_brand">히트정보</span>
  <em class="ssg_price">{formatted}</em>
  <p>상품번호 : 1000832367906</p>
</body></html>"""


def test_e2e_ssg_product_price_history_on_reingest(
    fake_db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()

    def override_get_firestore():
        yield fake_db

    app.dependency_overrides[get_firestore] = override_get_firestore
    test_client = TestClient(app)
    bridge = _TestClientIngestBridge(test_client, TEST_INGEST_API_KEY)
    parser = SSGProductParser()
    listing_id = "SSG_1000832367906"

    try:
        first = bridge.send_listing(
            parser.parse(
                _detail_html_with_price(1_599_000),
                PRODUCT_URL,
                crawled_at=datetime(2026, 8, 21, 10, 0, 0, tzinfo=timezone.utc),
            ).to_dict()
        )
        second = bridge.send_listing(
            parser.parse(
                _detail_html_with_price(1_549_000),
                PRODUCT_URL,
                crawled_at=datetime(2026, 8, 21, 11, 0, 0, tzinfo=timezone.utc),
            ).to_dict()
        )

        assert first["price_history_appended"] is True
        assert second["price_history_appended"] is True
        assert first["listing_id"] == listing_id
        assert second["listing_id"] == listing_id
        assert _history_count(fake_db, listing_id) == 2
        assert _latest_history_price(fake_db, listing_id) == 1_549_000

        history_prefix = f"{c.LISTINGS}/{listing_id}/{c.PRICE_HISTORY}/"
        history_prices = {
            int(fake_db.get_document(path)["price"])
            for path in fake_db.paths()
            if path.startswith(history_prefix)
        }
        assert history_prices == {1_599_000, 1_549_000}
    finally:
        app.dependency_overrides.clear()
        clear_settings_cache()
