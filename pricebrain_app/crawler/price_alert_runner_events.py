"""Structured price alert runner logging helpers."""

from __future__ import annotations

import logging
from typing import Any


def log_price_alert_runner_event(
    logger: logging.Logger,
    event: str,
    *,
    total_alerts: int | None = None,
    triggered: int | None = None,
    invalid: int | None = None,
    notification_failed: int | None = None,
    dry_run: bool | None = None,
    alert_id: str | None = None,
    target_id: str | None = None,
    message: str | None = None,
    **extra: Any,
) -> None:
    payload: dict[str, Any] = {"event": event}
    if total_alerts is not None:
        payload["total_alerts"] = total_alerts
    if triggered is not None:
        payload["triggered"] = triggered
    if invalid is not None:
        payload["invalid"] = invalid
    if notification_failed is not None:
        payload["notification_failed"] = notification_failed
    if dry_run is not None:
        payload["dry_run"] = dry_run
    if alert_id is not None:
        payload["alert_id"] = alert_id
    if target_id is not None:
        payload["target_id"] = target_id
    if message is not None:
        payload["message"] = message
    payload.update(extra)
    logger.info(event, extra=payload)
