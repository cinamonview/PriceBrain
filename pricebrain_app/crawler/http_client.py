"""HTTP client for mall crawlers — docs/07 §13–§14."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from pricebrain_app.crawler.exceptions import (
    CrawlerHTTPError,
    CrawlerRetryExhaustedError,
    CrawlerTimeoutError,
)
from pricebrain_app.crawler.retry import backoff_delay, should_retry_http_status

DEFAULT_USER_AGENT = (
    "PriceBrain/0.1 (research crawler; +https://github.com/pricebrain)"
)


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    text: str
    url: str


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
    ) -> None:
        self._timeout = timeout
        self._user_agent = user_agent
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._sleep_func = sleep_func
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout,
            headers={"User-Agent": user_agent},
            follow_redirects=True,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def get(self, url: str) -> HttpResponse:
        attempts = self._max_retries + 1
        last_error: Exception | None = None

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
                self._sleep_func(backoff_delay(attempt, self._backoff_seconds))
                continue

            if response.status_code == 200:
                return HttpResponse(
                    status_code=response.status_code,
                    text=response.text,
                    url=str(response.url),
                )

            if not should_retry_http_status(response.status_code):
                raise CrawlerHTTPError(
                    f"HTTP {response.status_code} for {url}",
                    status_code=response.status_code,
                    url=url,
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
            self._sleep_func(backoff_delay(attempt, self._backoff_seconds))

        raise CrawlerRetryExhaustedError(
            f"Retry exhausted for {url}",
            url=url,
            attempts=attempts,
        ) from last_error
