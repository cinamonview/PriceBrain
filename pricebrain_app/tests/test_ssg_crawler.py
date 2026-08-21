from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from pricebrain_app.crawler.exceptions import (
    CrawlerHTTPError,
    CrawlerRetryExhaustedError,
    CrawlerTimeoutError,
)
from pricebrain_app.crawler.http_client import HttpClient
from pricebrain_app.crawler.malls.ssg import SsgCrawler, build_ssg_search_url

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture_html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_build_ssg_search_url() -> None:
    url = build_ssg_search_url("RTX 5080")
    assert url.startswith("https://www.ssg.com/search.ssg?")
    assert "query=RTX+5080" in url or "query=RTX%205080" in url
    assert "target=all" in url


def test_ssg_crawler_search_with_mocked_http() -> None:
    html = _fixture_html("ssg_search_result.html")
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, text=html, request=request)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    http = HttpClient(client=client, sleep_func=lambda _: None)
    crawler = SsgCrawler(http_client=http)

    items = crawler.search("RTX 5080")
    assert call_count["n"] == 1
    assert len(items) == 2
    assert items[0]["product_id"] == "1000832367906"
    crawler.close()


def test_http_client_raises_on_non_retryable_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found", request=request)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    http = HttpClient(client=client, max_retries=2, sleep_func=lambda _: None)

    with pytest.raises(CrawlerHTTPError) as exc:
        http.get("https://example.test/search")
    assert exc.value.status_code == 404
    http.close()


def test_http_client_retries_then_succeeds() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(503, text="busy", request=request)
        return httpx.Response(200, text="ok", request=request)

    sleeps: list[float] = []
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    http = HttpClient(
        client=client,
        max_retries=3,
        backoff_seconds=(0.0, 0.0, 0.0),
        sleep_func=sleeps.append,
    )

    response = http.get("https://example.test/search")
    assert response.status_code == 200
    assert response.text == "ok"
    assert attempts["n"] == 3
    assert len(sleeps) == 2
    http.close()


def test_http_client_timeout_with_retry_exhaustion() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    http = HttpClient(
        client=client,
        max_retries=1,
        backoff_seconds=(0.0,),
        sleep_func=lambda _: None,
    )

    with pytest.raises(CrawlerTimeoutError):
        http.get("https://example.test/search")
    http.close()


def test_http_client_retry_exhausted_on_persistent_500() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="error", request=request)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    http = HttpClient(
        client=client,
        max_retries=2,
        backoff_seconds=(0.0, 0.0),
        sleep_func=lambda _: None,
    )

    with pytest.raises(CrawlerRetryExhaustedError):
        http.get("https://example.test/search")
    http.close()


def test_ssg_crawler_parse_search_html_only() -> None:
    crawler = SsgCrawler()
    items = crawler.parse_search_html(_fixture_html("ssg_search_result.html"))
    assert len(items) == 2
