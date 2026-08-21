"""Crawler operational stability tests — HTTP policy, batch, ingest, logging."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from pricebrain_app.crawler.adapters.ssg import SSGCrawler, SSGHtmlFetcher
from pricebrain_app.crawler.client import IngestClient
from pricebrain_app.crawler.config import clear_crawler_config_cache, parse_backoff_seconds
from pricebrain_app.crawler.exceptions import (
    CrawlerHTTPError,
    CrawlerRetryExhaustedError,
    CrawlerTimeoutError,
    IngestClientHTTPError,
    IngestClientNetworkError,
    IngestClientTimeoutError,
)
from pricebrain_app.crawler.http_client import HttpClient
from pricebrain_app.crawler.logging_utils import redact_secrets, safe_url_for_log
from pricebrain_app.crawler.operations import ingest_result
from pricebrain_app.crawler.results import CrawlerBatchSummary, CrawlerResult, CrawlerStatus

FIXTURES = Path(__file__).parent / "fixtures" / "ssg"
PRODUCT_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
OTHER_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000123456789"


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _mock_http(handler) -> HttpClient:
    transport = httpx.MockTransport(handler)
    return HttpClient(client=httpx.Client(transport=transport), sleep_func=lambda _: None)


def _success_payload_result() -> CrawlerResult:
    from pricebrain_app.crawler.models import IngestListingPayload

    crawled_at = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
    payload = IngestListingPayload(
        product_id="1000832367906",
        product_name="ZOTAC GAMING GeForce RTX 5080 16GB",
        mall_id="ssg",
        product_url=PRODUCT_URL,
        price=1_599_000,
        seller="히트정보",
        crawled_at=crawled_at,
    )
    return CrawlerResult(
        status=CrawlerStatus.SUCCESS,
        mall_id="ssg",
        product_url=PRODUCT_URL,
        external_product_id="1000832367906",
        message="crawl success",
        crawled_at=crawled_at.isoformat(),
        payload=payload,
    )


@pytest.mark.parametrize(
    ("status_code", "expected_attempts"),
    [
        (200, 1),
        (403, 1),
        (404, 1),
        (429, 3),
        (500, 3),
    ],
)
def test_http_status_retry_policy(status_code: int, expected_attempts: int) -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(status_code, text="body", request=request)

    http = HttpClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=2,
        backoff_seconds=(0.0, 0.0),
        sleep_func=lambda _: None,
    )

    if status_code == 200:
        response = http.get(PRODUCT_URL)
        assert response.status_code == 200
    elif status_code in {403, 404}:
        with pytest.raises(CrawlerHTTPError) as exc:
            http.get(PRODUCT_URL)
        assert exc.value.status_code == status_code
        if status_code == 403:
            assert exc.value.error_code == "SSG_ACCESS_DENIED"
    else:
        with pytest.raises(CrawlerRetryExhaustedError):
            http.get(PRODUCT_URL)

    assert attempts["n"] == expected_attempts
    http.close()


def test_http_timeout_retries_then_raises() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        raise httpx.TimeoutException("timed out", request=request)

    http = HttpClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=2,
        backoff_seconds=(0.0, 0.0),
        sleep_func=lambda _: None,
    )

    with pytest.raises(CrawlerTimeoutError):
        http.get(PRODUCT_URL)
    assert attempts["n"] == 3
    http.close()


def test_http_network_error_retries_then_raises() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        raise httpx.ConnectError("connection failed", request=request)

    http = HttpClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=2,
        backoff_seconds=(0.0, 0.0),
        sleep_func=lambda _: None,
    )

    with pytest.raises(CrawlerRetryExhaustedError):
        http.get(PRODUCT_URL)
    assert attempts["n"] == 3
    http.close()


def test_batch_continues_after_failures() -> None:
    html = _read_fixture("product_gpu.html")
    call_order: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        call_order.append(str(request.url))
        if "1000123456789" in str(request.url):
            return httpx.Response(403, text="denied", request=request)
        if "9999999999999" in str(request.url):
            return httpx.Response(200, text="<html></html>", request=request)
        return httpx.Response(200, text=html, request=request)

    fetcher = SSGHtmlFetcher(http_client=_mock_http(handler))
    crawler = SSGCrawler(fetcher=fetcher)

    urls = [
        PRODUCT_URL,
        OTHER_URL,
        "https://www.ssg.com/item/itemView.ssg?itemId=9999999999999",
        "",
        PRODUCT_URL,
    ]
    results, summary = crawler.crawl_urls_with_summary(urls)

    assert len(results) == 5
    assert results[0].status == CrawlerStatus.SUCCESS
    assert results[1].status == CrawlerStatus.HTTP_ERROR
    assert results[1].message == "SSG_ACCESS_DENIED"
    assert results[2].status == CrawlerStatus.PARSE_ERROR
    assert results[3].status == CrawlerStatus.SKIPPED
    assert results[4].status == CrawlerStatus.SUCCESS
    assert summary.total == 5
    assert summary.success == 2
    assert summary.http_error == 1
    assert summary.parse_error == 1
    assert summary.skipped == 1
    assert len(call_order) == 4
    crawler.close()


def test_batch_summary_counts() -> None:
    results = [
        CrawlerResult(status=CrawlerStatus.SUCCESS, mall_id="ssg"),
        CrawlerResult(status=CrawlerStatus.HTTP_ERROR, mall_id="ssg"),
        CrawlerResult(status=CrawlerStatus.INGEST_ERROR, mall_id="ssg"),
    ]
    summary = CrawlerBatchSummary.from_results(results)
    assert summary.total == 3
    assert summary.success == 1
    assert summary.http_error == 1
    assert summary.ingest_error == 1
    assert "success: 1" in summary.format_summary()


@pytest.mark.parametrize(
    ("side_effect", "expected_status", "expected_message"),
    [
        (lambda *_args, **_kwargs: {"status": "ok"}, CrawlerStatus.SUCCESS, "crawl and ingest success"),
        (
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                IngestClientHTTPError("422", status_code=422, detail="invalid")
            ),
            CrawlerStatus.INGEST_ERROR,
            "Ingest HTTP 422",
        ),
        (
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                IngestClientHTTPError("500", status_code=500, detail="error")
            ),
            CrawlerStatus.INGEST_ERROR,
            "Ingest HTTP 500",
        ),
        (
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                IngestClientTimeoutError("timeout", url="http://test")
            ),
            CrawlerStatus.INGEST_ERROR,
            "timeout",
        ),
        (
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                IngestClientNetworkError("network", url="http://test")
            ),
            CrawlerStatus.INGEST_ERROR,
            "network",
        ),
    ],
)
def test_ingest_result_isolated(
    side_effect: Any,
    expected_status: CrawlerStatus,
    expected_message: str,
) -> None:
    client = MagicMock(spec=IngestClient)
    client.send_listing.side_effect = side_effect
    result = ingest_result(_success_payload_result(), client)
    assert result.status == expected_status
    assert expected_message in result.message
    assert result.payload is not None


def test_dry_run_batch_does_not_call_ingest_client() -> None:
    html = _read_fixture("product_gpu.html")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, request=request)

    fetcher = SSGHtmlFetcher(http_client=_mock_http(handler))
    crawler = SSGCrawler(fetcher=fetcher)
    ingest_client = MagicMock(spec=IngestClient)

    results = crawler.crawl_urls([PRODUCT_URL], ingest=False, ingest_client=ingest_client)

    assert results[0].status == CrawlerStatus.SUCCESS
    ingest_client.send_listing.assert_not_called()
    crawler.close()


def test_batch_with_ingest_calls_client_once_per_success() -> None:
    html = _read_fixture("product_gpu.html")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, request=request)

    fetcher = SSGHtmlFetcher(http_client=_mock_http(handler))
    crawler = SSGCrawler(fetcher=fetcher)
    ingest_client = MagicMock(spec=IngestClient)
    ingest_client.send_listing.return_value = {"status": "ok", "listing_id": "SSG_x"}

    results = crawler.crawl_urls(
        [PRODUCT_URL, PRODUCT_URL],
        ingest=True,
        ingest_client=ingest_client,
    )

    assert all(result.status == CrawlerStatus.SUCCESS for result in results)
    assert ingest_client.send_listing.call_count == 2
    crawler.close()


def test_request_interval_applied_between_urls() -> None:
    html = _read_fixture("product_gpu.html")
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, request=request)

    fetcher = SSGHtmlFetcher(http_client=_mock_http(handler))
    crawler = SSGCrawler(fetcher=fetcher)

    crawler.crawl_urls_with_summary(
        [PRODUCT_URL, PRODUCT_URL],
        request_interval_seconds=1.5,
        sleep_func=sleeps.append,
    )

    assert sleeps == [1.5]
    crawler.close()


def test_safe_url_for_log_redacts_sensitive_query_and_keeps_item_id() -> None:
    url = (
        "https://www.ssg.com/item/itemView.ssg?"
        "itemId=1000832367906&token=secret-token&api_key=abc123"
    )
    safe = safe_url_for_log(url)
    assert "itemId=1000832367906" in safe
    assert "secret-token" not in safe
    assert "abc123" not in safe
    assert "token=***" in safe


def test_logs_do_not_contain_api_key(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="crawler.ssg")
    api_key = "super-secret-ingest-key"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="denied", request=request)

    fetcher = SSGHtmlFetcher(http_client=_mock_http(handler))
    crawler = SSGCrawler(fetcher=fetcher)
    crawler.crawl_product_url_result(PRODUCT_URL)
    crawler.close()

    combined = redact_secrets(caplog.text, [api_key])
    assert api_key not in combined
    assert "super-secret-ingest-key" not in caplog.text


def test_parse_backoff_seconds_single_value_expands() -> None:
    assert parse_backoff_seconds("1") == (1.0, 2.0, 4.0)
    assert parse_backoff_seconds("1,3,5") == (1.0, 3.0, 5.0)


def test_crawler_config_cache_can_be_cleared(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRICEBRAIN_CRAWLER_MAX_RETRIES", "1")
    from pricebrain_app.config.settings import clear_settings_cache
    from pricebrain_app.crawler.config import get_crawler_config

    clear_settings_cache()
    clear_crawler_config_cache()
    assert get_crawler_config().max_retries == 1
