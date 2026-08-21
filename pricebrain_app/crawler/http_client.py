"""HTTP client for mall crawlers — docs/07 §13–§14."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from pricebrain_app.crawler.exceptions import (
    CrawlerHTTPError,
    CrawlerRetryExhaustedError,
    CrawlerTimeoutError,
)
from pricebrain_app.crawler.logging_utils import safe_url_for_log
from pricebrain_app.crawler.retry import backoff_delay, should_retry_http_status

DEFAULT_USER_AGENT = (
    "PriceBrain/0.1 (research crawler; +https://github.com/pricebrain)"
)

logger = logging.getLogger("crawler.http")


def _http_error_code(status_code: int, url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower()
    if status_code == 403 and host.endswith("ssg.com"):
        return "SSG_ACCESS_DENIED"
    if status_code == 403:
        return "ACCESS_DENIED"
    if status_code == 404:
        return "NOT_FOUND"
    return None


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    text: str
    url: str
    retry_count: int = 0
    elapsed_ms: int = 0


class HttpClient:
    def __init__(
        self,
        *,
        timeout: float = 30.0,
        user_agent: str = DEFAULT_USER_AGENT,
        max_retries: int = 3,
        backoff_seconds: tuple[float, ...] = (1.0, 2.0, 4.0),
        client: httpx.Client | None = None,
        sleep_func: Callable[[float], None] = time.sleep,
        on_retry: Callable[[int, str, str], None] | None = None,
    ) -> None:
        self._timeout = timeout
        self._user_agent = user_agent
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._sleep_func = sleep_func
        self._on_retry = on_retry
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout,
            headers={"User-Agent": user_agent},
            follow_redirects=True,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _notify_retry(self, attempt: int, url: str, reason: str) -> None:
        if self._on_retry is not None:
            self._on_retry(attempt, url, reason)
            return
        logger.warning(
            "retrying request",
            extra={"attempt": attempt + 1, "url": safe_url_for_log(url), "reason": reason},
        )

    def get(self, url: str) -> HttpResponse:
        attempts = self._max_retries + 1
        last_error: Exception | None = None
        retry_count = 0
        started = time.perf_counter()

        for attempt in range(attempts):
            try:
                response = self._client.get(url, headers={"User-Agent": self._user_agent})
            except httpx.TimeoutException as exc:
                last_error = CrawlerTimeoutError(
                    f"Request timed out: {url}",
                    url=url,
                )
                if attempt >= self._max_retries:
                    raise last_error from exc
                self._notify_retry(attempt, url, "timeout")
                retry_count += 1
                self._sleep_func(backoff_delay(attempt, self._backoff_seconds))
                continue
            except httpx.RequestError as exc:
                last_error = CrawlerHTTPError(
                    f"Network error for {url}: {exc}",
                    url=url,
                )
                if attempt >= self._max_retries:
                    raise CrawlerRetryExhaustedError(
                        f"Retry exhausted for {url}",
                        url=url,
                        attempts=attempt + 1,
                    ) from exc
                self._notify_retry(attempt, url, "network")
                retry_count += 1
                self._sleep_func(backoff_delay(attempt, self._backoff_seconds))
                continue

            if response.status_code == 200:
                return HttpResponse(
                    status_code=response.status_code,
                    text=response.text,
                    url=str(response.url),
                    retry_count=retry_count,
                    elapsed_ms=int((time.perf_counter() - started) * 1000),
                )

            if not should_retry_http_status(response.status_code):
                raise CrawlerHTTPError(
                    f"HTTP {response.status_code} for {url}",
                    status_code=response.status_code,
                    url=url,
                    error_code=_http_error_code(response.status_code, url),
                )

            last_error = CrawlerHTTPError(
                f"HTTP {response.status_code} for {url}",
                status_code=response.status_code,
                url=url,
            )
            if attempt >= self._max_retries:
                raise CrawlerRetryExhaustedError(
                    f"Retry exhausted for {url} (last status {response.status_code})",
                    url=url,
                    attempts=attempt + 1,
                ) from last_error
            self._notify_retry(attempt, url, f"HTTP {response.status_code}")
            retry_count += 1
            self._sleep_func(backoff_delay(attempt, self._backoff_seconds))

        raise CrawlerRetryExhaustedError(
            f"Retry exhausted for {url}",
            url=url,
            attempts=attempts,
        ) from last_error
