"""Crawler batch operations — non-throwing results and ingest isolation."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from typing import Any

from pricebrain_app.crawler.client import IngestClient
from pricebrain_app.crawler.config import CrawlerConfig, get_crawler_config
from pricebrain_app.crawler.exceptions import (
    CrawlerError,
    CrawlerHTTPError,
    CrawlerParseError,
    CrawlerRetryExhaustedError,
    CrawlerTimeoutError,
    IngestClientError,
    IngestClientHTTPError,
    IngestClientNetworkError,
    IngestClientTimeoutError,
)
from pricebrain_app.crawler.logging_utils import get_crawler_logger, safe_url_for_log
from pricebrain_app.crawler.results import CrawlerBatchSummary, CrawlerResult, CrawlerStatus

logger = get_crawler_logger()


def http_error_code(status_code: int | None, url: str | None) -> str | None:
    if status_code == 403 and url and "ssg.com" in url.lower():
        return "SSG_ACCESS_DENIED"
    if status_code == 403:
        return "ACCESS_DENIED"
    if status_code == 404:
        return "NOT_FOUND"
    return None


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def map_crawler_error_to_result(
    exc: Exception,
    *,
    mall_id: str,
    product_url: str | None,
    elapsed_ms: int,
    retry_count: int = 0,
) -> CrawlerResult:
    if isinstance(exc, CrawlerHTTPError):
        code = exc.error_code or http_error_code(exc.status_code, exc.url or product_url)
        message = code or str(exc)
        logger.warning(
            "HTTP %s",
            exc.status_code,
            extra={"url": safe_url_for_log(product_url or exc.url)},
        )
        return CrawlerResult(
            status=CrawlerStatus.HTTP_ERROR,
            mall_id=mall_id,
            product_url=product_url,
            message=message,
            retry_count=retry_count,
            elapsed_ms=elapsed_ms,
            http_status_code=exc.status_code,
        )

    if isinstance(exc, CrawlerTimeoutError):
        logger.warning("request timeout", extra={"url": safe_url_for_log(product_url)})
        return CrawlerResult(
            status=CrawlerStatus.TIMEOUT,
            mall_id=mall_id,
            product_url=product_url,
            message=str(exc),
            retry_count=retry_count,
            elapsed_ms=elapsed_ms,
        )

    if isinstance(exc, CrawlerRetryExhaustedError):
        cause = exc.__cause__
        attempts = exc.attempts or retry_count
        if isinstance(cause, CrawlerTimeoutError):
            status = CrawlerStatus.TIMEOUT
        elif isinstance(cause, CrawlerHTTPError):
            if cause.status_code and cause.status_code >= 500:
                status = CrawlerStatus.HTTP_ERROR
            else:
                status = CrawlerStatus.NETWORK_ERROR
        else:
            status = CrawlerStatus.NETWORK_ERROR
        logger.warning(
            "retry exhausted",
            extra={"url": safe_url_for_log(product_url), "attempts": attempts},
        )
        http_status = cause.status_code if isinstance(cause, CrawlerHTTPError) else None
        return CrawlerResult(
            status=status,
            mall_id=mall_id,
            product_url=product_url,
            message=str(exc),
            retry_count=max(attempts - 1, 0),
            elapsed_ms=elapsed_ms,
            http_status_code=http_status,
        )

    if isinstance(exc, CrawlerParseError):
        logger.error("parse failed", extra={"url": safe_url_for_log(product_url)})
        return CrawlerResult(
            status=CrawlerStatus.PARSE_ERROR,
            mall_id=mall_id,
            product_url=product_url,
            message=str(exc),
            retry_count=retry_count,
            elapsed_ms=elapsed_ms,
        )

    if isinstance(exc, ValueError):
        logger.warning("validation failed", extra={"url": safe_url_for_log(product_url)})
        return CrawlerResult(
            status=CrawlerStatus.VALIDATION_ERROR,
            mall_id=mall_id,
            product_url=product_url,
            message=str(exc),
            retry_count=retry_count,
            elapsed_ms=elapsed_ms,
        )

    if isinstance(exc, CrawlerError):
        return CrawlerResult(
            status=CrawlerStatus.NETWORK_ERROR,
            mall_id=mall_id,
            product_url=product_url,
            message=str(exc),
            retry_count=retry_count,
            elapsed_ms=elapsed_ms,
        )

    return CrawlerResult(
        status=CrawlerStatus.NETWORK_ERROR,
        mall_id=mall_id,
        product_url=product_url,
        message=str(exc),
        retry_count=retry_count,
        elapsed_ms=elapsed_ms,
    )


def ingest_result(
    crawl_result: CrawlerResult,
    client: IngestClient,
) -> CrawlerResult:
    if crawl_result.status != CrawlerStatus.SUCCESS or crawl_result.payload is None:
        return crawl_result

    try:
        response = client.send_listing(crawl_result.payload.to_dict())
    except IngestClientHTTPError as exc:
        logger.error("ingest failed", extra={"http_status": exc.status_code})
        return CrawlerResult(
            status=CrawlerStatus.INGEST_ERROR,
            mall_id=crawl_result.mall_id,
            product_url=crawl_result.product_url,
            external_product_id=crawl_result.external_product_id,
            message=f"Ingest HTTP {exc.status_code}",
            retry_count=crawl_result.retry_count,
            elapsed_ms=crawl_result.elapsed_ms,
            crawled_at=crawl_result.crawled_at,
            http_status_code=exc.status_code,
            payload=crawl_result.payload,
        )
    except IngestClientTimeoutError as exc:
        logger.error("ingest timeout")
        return CrawlerResult(
            status=CrawlerStatus.INGEST_ERROR,
            mall_id=crawl_result.mall_id,
            product_url=crawl_result.product_url,
            external_product_id=crawl_result.external_product_id,
            message=str(exc),
            retry_count=crawl_result.retry_count,
            elapsed_ms=crawl_result.elapsed_ms,
            crawled_at=crawl_result.crawled_at,
            payload=crawl_result.payload,
        )
    except IngestClientNetworkError as exc:
        logger.error("ingest network error")
        return CrawlerResult(
            status=CrawlerStatus.INGEST_ERROR,
            mall_id=crawl_result.mall_id,
            product_url=crawl_result.product_url,
            external_product_id=crawl_result.external_product_id,
            message=str(exc),
            retry_count=crawl_result.retry_count,
            elapsed_ms=crawl_result.elapsed_ms,
            crawled_at=crawl_result.crawled_at,
            payload=crawl_result.payload,
        )
    except IngestClientError as exc:
        logger.error("ingest failed")
        return CrawlerResult(
            status=CrawlerStatus.INGEST_ERROR,
            mall_id=crawl_result.mall_id,
            product_url=crawl_result.product_url,
            external_product_id=crawl_result.external_product_id,
            message=str(exc),
            retry_count=crawl_result.retry_count,
            elapsed_ms=crawl_result.elapsed_ms,
            crawled_at=crawl_result.crawled_at,
            payload=crawl_result.payload,
        )

    if response.get("status") == "quarantined":
        logger.warning(
            "ingest quarantined", extra={"gpu_model_id": response.get("gpu_model_id")}
        )
        return CrawlerResult(
            status=CrawlerStatus.QUARANTINED,
            mall_id=crawl_result.mall_id,
            product_url=crawl_result.product_url,
            external_product_id=crawl_result.external_product_id,
            message=f"unknown GPU model quarantined: {response.get('gpu_model_id')}",
            retry_count=crawl_result.retry_count,
            elapsed_ms=crawl_result.elapsed_ms,
            crawled_at=crawl_result.crawled_at,
            payload=crawl_result.payload,
            ingest_response=response,
        )

    logger.info("ingest success", extra={"listing_id": response.get("listing_id")})
    return CrawlerResult(
        status=CrawlerStatus.SUCCESS,
        mall_id=crawl_result.mall_id,
        product_url=crawl_result.product_url,
        external_product_id=crawl_result.external_product_id,
        message="crawl and ingest success",
        retry_count=crawl_result.retry_count,
        elapsed_ms=crawl_result.elapsed_ms,
        crawled_at=crawl_result.crawled_at,
        payload=crawl_result.payload,
        ingest_response=response,
    )


def run_url_batch(
    *,
    mall_id: str,
    urls: Iterable[str],
    crawl_one: Callable[[str], CrawlerResult],
    ingest: bool = False,
    ingest_client: IngestClient | None = None,
    request_interval_seconds: float | None = None,
    config: CrawlerConfig | None = None,
    sleep_func: Callable[[float], None] = time.sleep,
) -> tuple[list[CrawlerResult], CrawlerBatchSummary]:
    cfg = config or get_crawler_config()
    interval = (
        request_interval_seconds
        if request_interval_seconds is not None
        else cfg.request_interval_seconds
    )

    results: list[CrawlerResult] = []
    for index, raw_url in enumerate(urls):
        url = raw_url.strip()
        if not url or url.startswith("#"):
            results.append(
                CrawlerResult(
                    status=CrawlerStatus.SKIPPED,
                    mall_id=mall_id,
                    product_url=raw_url,
                    message="empty or comment line",
                )
            )
            continue

        if index > 0 and interval > 0:
            sleep_func(interval)

        result = crawl_one(url)
        if ingest and result.status == CrawlerStatus.SUCCESS:
            if ingest_client is None:
                result = CrawlerResult(
                    status=CrawlerStatus.INGEST_ERROR,
                    mall_id=mall_id,
                    product_url=result.product_url,
                    external_product_id=result.external_product_id,
                    message="IngestClient is required when ingest=True",
                    retry_count=result.retry_count,
                    elapsed_ms=result.elapsed_ms,
                    crawled_at=result.crawled_at,
                    payload=result.payload,
                )
            else:
                result = ingest_result(result, ingest_client)
        results.append(result)

    return results, CrawlerBatchSummary.from_results(results)
