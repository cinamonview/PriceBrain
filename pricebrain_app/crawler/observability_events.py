"""Structured crawler observability logging helpers."""

from __future__ import annotations

import logging
from typing import Any

from pricebrain_app.crawler.logging_utils import safe_url_for_log


def log_observability_event(
    logger: logging.Logger,
    event: str,
    *,
    target_id: str | None = None,
    mall_id: str | None = None,
    status: str | None = None,
    error_code: str | None = None,
    elapsed_ms: int | None = None,
    price: int | None = None,
    product_url: str | None = None,
    **extra: Any,
) -> None:
    payload: dict[str, Any] = {"event": event}
    if target_id is not None:
        payload["target_id"] = target_id
    if mall_id is not None:
        payload["mall_id"] = mall_id
    if status is not None:
        payload["status"] = status
    if error_code is not None:
        payload["error_code"] = error_code
    if elapsed_ms is not None:
        payload["elapsed_ms"] = elapsed_ms
    if price is not None:
        payload["price"] = price
    if product_url is not None:
        payload["url"] = safe_url_for_log(product_url)
    payload.update(extra)
    logger.info(event, extra=payload)


def crawl_event_for_status(status: str) -> str:
    mapping = {
        "SUCCESS": "crawl_success",
        "HTTP_ERROR": "crawl_http_error",
        "PARSE_ERROR": "crawl_parse_error",
        "TIMEOUT": "crawl_timeout",
        "NETWORK_ERROR": "crawl_network_error",
        "INGEST_ERROR": "ingest_error",
        "VALIDATION_ERROR": "crawl_parse_error",
    }
    return mapping.get(status, "crawl_started")
