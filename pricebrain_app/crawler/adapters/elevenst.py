"""11번가 mall ingest adapter — fetch HTML → parse → IngestListingPayload."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pricebrain_app.crawler.adapters.ssg import _raise_from_result
from pricebrain_app.crawler.base import BaseCrawler
from pricebrain_app.crawler.config import build_http_client, get_crawler_config
from pricebrain_app.crawler.exceptions import CrawlerHTTPError, CrawlerParseError
from pricebrain_app.crawler.http_client import HttpClient, HttpResponse
from pricebrain_app.crawler.logging_utils import get_crawler_logger, safe_url_for_log
from pricebrain_app.crawler.malls.elevenst import (
    build_elevenst_search_url,
    validate_elevenst_product_url,
)
from pricebrain_app.crawler.models import (
    IngestListingPayload,
    ingest_payload_from_raw,
    utc_now_crawled_at,
)
from pricebrain_app.crawler.operations import map_crawler_error_to_result
from pricebrain_app.crawler.parser.elevenst import parse_elevenst_product_detail_html
from pricebrain_app.crawler.parser.elevenst_search import parse_elevenst_search_json
from pricebrain_app.crawler.results import CrawlerResult, CrawlerStatus
from pricebrain_app.crawler.types import RawProductData

logger = get_crawler_logger()


def _default_elevenst_http_client() -> HttpClient:
    return build_http_client()


class ElevenstHtmlFetcher:
    """Fetch 11번가 HTML — HTTP only, no parsing."""

    def __init__(self, http_client: HttpClient | None = None) -> None:
        self._http = http_client or _default_elevenst_http_client()
        self._owns_client = http_client is None
        self._last_response: HttpResponse | None = None

    @property
    def last_response(self) -> HttpResponse | None:
        return self._last_response

    def fetch_product_html(self, product_url: str) -> str:
        url = validate_elevenst_product_url(product_url)
        response = self._http.get(url)
        self._last_response = response
        if response.status_code != 200:
            raise CrawlerHTTPError(
                f"Unexpected HTTP status {response.status_code}",
                status_code=response.status_code,
                url=url,
            )
        return response.text

    def fetch_search_json(self, keyword: str, *, page: int = 1) -> dict[str, Any]:
        """Fetch one 11번가 search page as JSON."""
        url = build_elevenst_search_url(keyword, page=page)
        response = self._http.get(url)
        self._last_response = response
        if response.status_code != 200:
            raise CrawlerHTTPError(
                f"Unexpected HTTP status {response.status_code}",
                status_code=response.status_code,
                url=url,
            )
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as exc:
            raise CrawlerParseError(
                f"11번가 search response was not JSON: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise CrawlerParseError("11번가 search response was not a JSON object")
        return payload

    def close(self) -> None:
        if self._owns_client:
            self._http.close()


class ElevenstProductParser:
    """Parse 11번가 HTML into ingest payloads — no HTTP, no Firestore."""

    def parse(
        self,
        html: str,
        url: str,
        *,
        crawled_at: datetime | None = None,
    ) -> IngestListingPayload:
        raw = parse_elevenst_product_detail_html(
            html,
            mall="ELEVENST",
            product_url=url,
            crawled_at=crawled_at,
        )
        if raw is None:
            raise CrawlerParseError("11번가 HTML did not contain a parseable product")
        try:
            return ingest_payload_from_raw(dict(raw))
        except ValueError as exc:
            raise CrawlerParseError(
                f"11번가 parse produced invalid ingest payload: {exc}"
            ) from exc


class ElevenstCrawler(BaseCrawler):
    """11번가 adapter: single product URL → payload for ingest API."""

    mall_id = "elevenst"

    def __init__(
        self,
        *,
        fetcher: ElevenstHtmlFetcher | None = None,
        parser: ElevenstProductParser | None = None,
    ) -> None:
        self._fetcher = fetcher or ElevenstHtmlFetcher()
        self._owns_fetcher = fetcher is None
        self._parser = parser or ElevenstProductParser()

    def crawl(self, product_url: str = "") -> list[IngestListingPayload]:
        if not product_url:
            raise CrawlerParseError("product_url is required for 11번가 crawl")
        return [self.crawl_product_url(product_url)]

    def search(
        self,
        keyword: str,
        *,
        page: int = 1,
        crawled_at: datetime | None = None,
    ) -> list[RawProductData]:
        """Fetch one search page and return raw products (docs/07 §3 boundary).

        Returns RawProductData rather than ingest payloads so the search batch can
        classify items the ingest payload contract would reject outright.
        """
        payload = self._fetcher.fetch_search_json(keyword, page=page)
        return parse_elevenst_search_json(
            payload,
            mall="ELEVENST",
            crawled_at=crawled_at or utc_now_crawled_at(),
        )

    def crawl_product_url(self, product_url: str) -> IngestListingPayload:
        result = self.crawl_product_url_result(product_url)
        if result.status != CrawlerStatus.SUCCESS or result.payload is None:
            if result.status == CrawlerStatus.PARSE_ERROR:
                raise CrawlerParseError(result.message)
            raise _raise_from_result(result)
        return result.payload

    def crawl_product_url_result(self, product_url: str) -> CrawlerResult:
        import time

        started = time.perf_counter()
        safe_url = safe_url_for_log(product_url)
        logger.info("crawling product", extra={"url": safe_url})

        try:
            url = validate_elevenst_product_url(product_url)
        except ValueError as exc:
            return map_crawler_error_to_result(
                exc,
                mall_id=self.mall_id,
                product_url=product_url,
                elapsed_ms=int((time.perf_counter() - started) * 1000),
            )

        try:
            html = self._fetcher.fetch_product_html(url)
            payload = self._parser.parse(html, url, crawled_at=utc_now_crawled_at())
            last_response = self._fetcher.last_response
            retry_count = last_response.retry_count if last_response else 0
            elapsed_ms = last_response.elapsed_ms if last_response else int(
                (time.perf_counter() - started) * 1000
            )
            logger.info(
                "crawl success",
                extra={
                    "url": safe_url_for_log(url),
                    "external_product_id": payload.product_id,
                },
            )
            return CrawlerResult(
                status=CrawlerStatus.SUCCESS,
                mall_id=self.mall_id,
                product_url=url,
                external_product_id=payload.product_id,
                message="crawl success",
                retry_count=retry_count,
                elapsed_ms=elapsed_ms,
                crawled_at=payload.crawled_at.isoformat(),
                payload=payload,
            )
        except Exception as exc:
            last_response = self._fetcher.last_response
            retry_count = last_response.retry_count if last_response else 0
            return map_crawler_error_to_result(
                exc,
                mall_id=self.mall_id,
                product_url=url,
                elapsed_ms=int((time.perf_counter() - started) * 1000),
                retry_count=retry_count,
            )

    def close(self) -> None:
        if self._owns_fetcher:
            self._fetcher.close()

    def __enter__(self) -> ElevenstCrawler:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
