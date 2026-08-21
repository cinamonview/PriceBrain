"""Structured price alert logging helpers."""

from __future__ import annotations

import logging
from typing import Any

from pricebrain_app.crawler.logging_utils import safe_url_for_log


def log_price_alert_event(
    logger: logging.Logger,
    event: str,
    *,
    alert_id: str | None = None,
    target_id: str | None = None,
    mall_id: str | None = None,
    alert_type: str | None = None,
    outcome: str | None = None,
    current_price: int | None = None,
    previous_price: int | None = None,
    threshold: float | None = None,
    product_url: str | None = None,
    message: str | None = None,
    **extra: Any,
) -> None:
    payload: dict[str, Any] = {"event": event}
    if alert_id is not None:
        payload["alert_id"] = alert_id
    if target_id is not None:
        payload["target_id"] = target_id
    if mall_id is not None:
        payload["mall_id"] = mall_id
    if alert_type is not None:
        payload["alert_type"] = alert_type
    if outcome is not None:
        payload["outcome"] = outcome
    if current_price is not None:
        payload["current_price"] = current_price
    if previous_price is not None:
        payload["previous_price"] = previous_price
    if threshold is not None:
        payload["threshold"] = threshold
    if message is not None:
        payload["message"] = message
    if product_url is not None:
        payload["url"] = safe_url_for_log(product_url)
    payload.update(extra)
    logger.info(event, extra=payload)
