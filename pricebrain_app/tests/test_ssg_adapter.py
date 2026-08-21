"""SSG ingest adapter tests — fixture HTML and mocked HTTP only."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from pricebrain_app.crawler.adapters.ssg import SSGCrawler, SSGHtmlFetcher, SSGProductParser
from pricebrain_app.crawler.exceptions import CrawlerHTTPError, CrawlerParseError
from pricebrain_app.crawler.http_client import HttpClient

FIXTURES = Path(__file__).parent / "fixtures" / "ssg"


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_ssg_product_parser_extracts_fields_from_fixture() -> None:
    parser = SSGProductParser()
    payload = parser.parse(
        _read_fixture("product_gpu.html"),
        url="https://www.ssg.com/item/itemView.ssg?itemId=1000832367906",
    )

    assert payload.product_id == "1000832367906"
    assert "RTX 5080" in payload.product_name
    assert payload.mall_id == "ssg"
    assert payload.price == 2_429_000
    assert payload.seller == "히트정보"
    assert "ssg.com/item/itemView.ssg" in payload.product_url
    assert payload.crawled_at is not None


def test_ssg_product_parser_raises_on_empty_html() -> None:
    parser = SSGProductParser()
    with pytest.raises(CrawlerParseError, match="did not contain a parseable product"):
        parser.parse("<html><body></body></html>", url="https://example.com")


def test_ssg_crawler_parse_html_offline() -> None:
    crawler = SSGCrawler(fetcher=SSGHtmlFetcher(http_client=_noop_http()))
    payloads = crawler.parse_html(_read_fixture("product_gpu.html"))
    assert len(payloads) == 1
    assert payloads[0].mall_id == "ssg"


def test_ssg_crawler_crawl_with_mocked_http() -> None:
    html = _read_fixture("product_gpu.html")
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, text=html, request=request)

    transport = httpx.MockTransport(handler)
    http = HttpClient(client=httpx.Client(transport=transport), sleep_func=lambda _: None)
    fetcher = SSGHtmlFetcher(http_client=http)
    crawler = SSGCrawler(fetcher=fetcher)

    payloads = crawler.crawl("RTX 5080")
    assert call_count["n"] == 1
    assert len(payloads) == 1
    assert payloads[0].product_id == "1000832367906"
    crawler.close()


def test_ssg_html_fetcher_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found", request=request)

    transport = httpx.MockTransport(handler)
    http = HttpClient(client=httpx.Client(transport=transport), sleep_func=lambda _: None)
    fetcher = SSGHtmlFetcher(http_client=http)

    with pytest.raises(CrawlerHTTPError) as exc_info:
        fetcher.fetch_search_html("RTX 5080")
    assert exc_info.value.status_code == 404
    fetcher.close()


def _noop_http() -> HttpClient:
    def handler(request: httpx.Request) -> httpx.Response:
        raise RuntimeError("HTTP should not be called in offline parse test")

    transport = httpx.MockTransport(handler)
    return HttpClient(client=httpx.Client(transport=transport), sleep_func=lambda _: None)
