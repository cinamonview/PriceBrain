"""Structured notification logging helpers."""

from __future__ import annotations

import logging
from typing import Any

from pricebrain_app.crawler.logging_utils import safe_url_for_log


def log_notification_event(
    logger: logging.Logger,
    event: str,
    *,
    notification_id: str | None = None,
    alert_id: str | None = None,
    target_id: str | None = None,
    mall_id: str | None = None,
    channel: str | None = None,
    status: str | None = None,
    message: str | None = None,
    product_url: str | None = None,
    **extra: Any,
) -> None:
    payload: dict[str, Any] = {"event": event}
    if notification_id is not None:
        payload["notification_id"] = notification_id
    if alert_id is not None:
        payload["alert_id"] = alert_id
    if target_id is not None:
        payload["target_id"] = target_id
    if mall_id is not None:
        payload["mall_id"] = mall_id
    if channel is not None:
        payload["channel"] = channel
    if status is not None:
        payload["status"] = status
    if message is not None:
        payload["message"] = message
    if product_url is not None:
        payload["url"] = safe_url_for_log(product_url)
    payload.update(extra)
    logger.info(event, extra=payload)
