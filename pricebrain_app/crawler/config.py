"""Crawler runtime configuration — env-driven HTTP/retry/interval policy."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from pricebrain_app.config.settings import get_settings
from pricebrain_app.crawler.http_client import HttpClient


def parse_backoff_seconds(
    raw: str,
    *,
    default: tuple[float, ...] = (1.0, 2.0, 4.0),
) -> tuple[float, ...]:
    text = raw.strip()
    if not text:
        return default
    parts = [float(part.strip()) for part in text.split(",") if part.strip()]
    if not parts:
        return default
    if len(parts) == 1:
        base = parts[0]
        return (base, base * 2, base * 4)
    return tuple(parts)


@dataclass(frozen=True)
class CrawlerConfig:
    timeout_seconds: float = 15.0
    max_retries: int = 2
    backoff_seconds: tuple[float, ...] = (1.0, 2.0, 4.0)
    request_interval_seconds: float = 0.0


@dataclass(frozen=True)
class WorkerConfig:
    enabled: bool = True
    poll_interval_seconds: float = 60.0
    max_targets_per_cycle: int = 10
    lease_seconds: int = 300


@lru_cache
def get_crawler_config() -> CrawlerConfig:
    settings = get_settings()
    return CrawlerConfig(
        timeout_seconds=settings.pricebrain_crawler_timeout_seconds,
        max_retries=settings.pricebrain_crawler_max_retries,
        backoff_seconds=parse_backoff_seconds(settings.pricebrain_crawler_backoff_seconds),
        request_interval_seconds=settings.pricebrain_crawler_request_interval_seconds,
    )


@lru_cache
def get_worker_config() -> WorkerConfig:
    settings = get_settings()
    return WorkerConfig(
        enabled=settings.pricebrain_crawler_worker_enabled,
        poll_interval_seconds=settings.pricebrain_crawler_poll_interval_seconds,
        max_targets_per_cycle=settings.pricebrain_crawler_max_targets_per_cycle,
        lease_seconds=settings.pricebrain_crawler_lease_seconds,
    )


def clear_crawler_config_cache() -> None:
    get_crawler_config.cache_clear()
    get_worker_config.cache_clear()


def build_http_client(
    *,
    timeout: float | None = None,
    max_retries: int | None = None,
    backoff_seconds: tuple[float, ...] | None = None,
    client=None,
    sleep_func=None,
    on_retry=None,
) -> HttpClient:
    config = get_crawler_config()
    kwargs: dict = {
        "timeout": timeout if timeout is not None else config.timeout_seconds,
        "max_retries": max_retries if max_retries is not None else config.max_retries,
        "backoff_seconds": (
            backoff_seconds if backoff_seconds is not None else config.backoff_seconds
        ),
    }
    if client is not None:
        kwargs["client"] = client
    if sleep_func is not None:
        kwargs["sleep_func"] = sleep_func
    if on_retry is not None:
        kwargs["on_retry"] = on_retry
    return HttpClient(**kwargs)
