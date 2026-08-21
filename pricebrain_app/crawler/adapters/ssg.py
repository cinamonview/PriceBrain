"""SSG mall ingest adapter — fetch HTML → parse → IngestListingPayload."""

from __future__ import annotations

from datetime import datetime

from pricebrain_app.crawler.base import BaseCrawler
from pricebrain_app.crawler.client import IngestClient
from pricebrain_app.crawler.config import build_http_client, get_crawler_config
from pricebrain_app.crawler.exceptions import (
    CrawlerHTTPError,
    CrawlerParseError,
    CrawlerRetryExhaustedError,
)
from pricebrain_app.crawler.http_client import HttpClient, HttpResponse
from pricebrain_app.crawler.logging_utils import get_crawler_logger, safe_url_for_log
from pricebrain_app.crawler.malls.ssg import build_ssg_search_url, validate_ssg_product_url
from pricebrain_app.crawler.models import (
    IngestListingPayload,
    ingest_payload_from_raw,
    utc_now_crawled_at,
)
from pricebrain_app.crawler.operations import map_crawler_error_to_result, run_url_batch
from pricebrain_app.crawler.parser.ssg import (
    parse_ssg_product_page_html,
    parse_ssg_search_html,
)
from pricebrain_app.crawler.results import CrawlerBatchSummary, CrawlerResult, CrawlerStatus

logger = get_crawler_logger()


def _default_ssg_http_client() -> HttpClient:
    return build_http_client()


class SSGHtmlFetcher:
    """Fetch SSG HTML — HTTP only, no parsing."""

    def __init__(self, http_client: HttpClient | None = None) -> None:
        self._http = http_client or _default_ssg_http_client()
        self._owns_client = http_client is None
        self._last_response: HttpResponse | None = None

    @property
    def last_response(self) -> HttpResponse | None:
        return self._last_response

    def _fetch_html(self, url: str) -> str:
        response = self._http.get(url)
        self._last_response = response
        if response.status_code != 200:
            raise CrawlerHTTPError(
                f"Unexpected HTTP status {response.status_code}",
                status_code=response.status_code,
                url=url,
            )
        return response.text

    def fetch_search_html(self, keyword: str) -> str:
        url = build_ssg_search_url(keyword)
        return self._fetch_html(url)

    def fetch_product_html(self, product_url: str) -> str:
        url = validate_ssg_product_url(product_url)
        return self._fetch_html(url)

    def close(self) -> None:
        if self._owns_client:
            self._http.close()


class SSGProductParser:
    """Parse SSG HTML into ingest payloads — no HTTP, no Firestore."""

    def parse_search_html(
        self,
        html: str,
        *,
        crawled_at: datetime | None = None,
    ) -> list[IngestListingPayload]:
        raw_items = parse_ssg_search_html(html, mall="SSG", crawled_at=crawled_at)
        payloads: list[IngestListingPayload] = []
        for raw in raw_items:
            try:
                payloads.append(ingest_payload_from_raw(dict(raw)))
            except ValueError as exc:
                raise CrawlerParseError(
                    f"SSG parse produced invalid ingest payload: {exc}"
                ) from exc
        return payloads

    def parse(
        self,
        html: str,
        url: str,
        *,
        crawled_at: datetime | None = None,
    ) -> IngestListingPayload:
        """Parse a single-product HTML page (search unit or product detail page)."""
        collected_at = crawled_at or utc_now_crawled_at()
        raw = parse_ssg_product_page_html(
            html,
            mall="SSG",
            product_url=url,
            crawled_at=collected_at,
        )
        if raw is None:
            raise CrawlerParseError("SSG HTML did not contain a parseable product")
        try:
            return ingest_payload_from_raw(dict(raw))
        except ValueError as exc:
            raise CrawlerParseError(
                f"SSG parse produced invalid ingest payload: {exc}"
            ) from exc


class SSGCrawler(BaseCrawler):
    """SSG adapter: search or single product URL → payloads for ingest API."""

    mall_id = "ssg"

    def __init__(
        self,
        *,
        fetcher: SSGHtmlFetcher | None = None,
        parser: SSGProductParser | None = None,
    ) -> None:
        self._fetcher = fetcher or SSGHtmlFetcher()
        self._owns_fetcher = fetcher is None
        self._parser = parser or SSGProductParser()

    def crawl(self, keyword: str = "RTX 5080") -> list[IngestListingPayload]:
        html = self._fetcher.fetch_search_html(keyword)
        return self._parser.parse_search_html(html, crawled_at=utc_now_crawled_at())

    def crawl_product(self, keyword: str = "RTX 5080") -> IngestListingPayload:
        payloads = self.crawl(keyword)
        if not payloads:
            raise CrawlerParseError(f"No SSG products parsed for keyword: {keyword}")
        return payloads[0]

    def crawl_product_url(self, product_url: str) -> IngestListingPayload:
        """Fetch one SSG product URL and return a single ingest payload."""
        result = self.crawl_product_url_result(product_url)
        if result.status != CrawlerStatus.SUCCESS or result.payload is None:
            raise CrawlerParseError(result.message) if result.status == CrawlerStatus.PARSE_ERROR else _raise_from_result(result)
        return result.payload

    def crawl_product_url_result(self, product_url: str) -> CrawlerResult:
        """Fetch and parse one URL without raising on operational failures."""
        import time

        started = time.perf_counter()
        safe_url = safe_url_for_log(product_url)
        logger.info("crawling product", extra={"url": safe_url})

        try:
            url = validate_ssg_product_url(product_url)
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
            if isinstance(exc, CrawlerRetryExhaustedError):
                retry_count = max(exc.attempts - 1, retry_count)
            return map_crawler_error_to_result(
                exc,
                mall_id=self.mall_id,
                product_url=url,
                elapsed_ms=int((time.perf_counter() - started) * 1000),
                retry_count=retry_count,
            )

    def crawl_urls(
        self,
        urls: list[str],
        *,
        ingest: bool = False,
        ingest_client: IngestClient | None = None,
        request_interval_seconds: float | None = None,
    ) -> list[CrawlerResult]:
        """Process URLs sequentially; failures do not stop the batch."""
        results, _summary = self.crawl_urls_with_summary(
            urls,
            ingest=ingest,
            ingest_client=ingest_client,
            request_interval_seconds=request_interval_seconds,
        )
        return results

    def crawl_urls_with_summary(
        self,
        urls: list[str],
        *,
        ingest: bool = False,
        ingest_client: IngestClient | None = None,
        request_interval_seconds: float | None = None,
        sleep_func=None,
    ) -> tuple[list[CrawlerResult], CrawlerBatchSummary]:
        import time

        return run_url_batch(
            mall_id=self.mall_id,
            urls=urls,
            crawl_one=self.crawl_product_url_result,
            ingest=ingest,
            ingest_client=ingest_client,
            request_interval_seconds=request_interval_seconds,
            config=get_crawler_config(),
            sleep_func=sleep_func or time.sleep,
        )

    def parse_html(self, html: str) -> list[IngestListingPayload]:
        """Parse fixture/offline HTML without HTTP."""
        return self._parser.parse_search_html(html, crawled_at=utc_now_crawled_at())

    def close(self) -> None:
        if self._owns_fetcher:
            self._fetcher.close()

    def __enter__(self) -> SSGCrawler:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _raise_from_result(result: CrawlerResult) -> IngestListingPayload:
    from pricebrain_app.crawler.exceptions import CrawlerRetryExhaustedError, CrawlerTimeoutError

    if result.status == CrawlerStatus.HTTP_ERROR:
        raise CrawlerHTTPError(
            result.message,
            status_code=result.http_status_code,
            url=result.product_url,
            error_code=result.message
            if result.message in {"SSG_ACCESS_DENIED", "ACCESS_DENIED", "NOT_FOUND"}
            else None,
        )
    if result.status == CrawlerStatus.TIMEOUT:
        raise CrawlerTimeoutError(result.message, url=result.product_url)
    if result.status == CrawlerStatus.VALIDATION_ERROR:
        raise ValueError(result.message)
    if result.status == CrawlerStatus.PARSE_ERROR:
        raise CrawlerParseError(result.message)
    if result.status == CrawlerStatus.NETWORK_ERROR:
        raise CrawlerRetryExhaustedError(
            result.message,
            url=result.product_url,
            attempts=result.retry_count + 1,
        )
    raise CrawlerParseError(result.message)
