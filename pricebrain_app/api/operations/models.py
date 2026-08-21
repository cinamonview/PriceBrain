"""Shared query/response helpers for read-only operations API."""

from __future__ import annotations

import json
from typing import Any

from pricebrain_app.crawler.dashboard_operations_models import DashboardFilter
from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction
from pricebrain_app.crawler.logging_utils import redact_secrets

READ_ONLY_DESCRIPTION = (
    "Read-only operations endpoint. Does not execute crawler, runner, notification, "
    "alert, or remediation actions."
)


def dashboard_filter(
    *,
    category: str | None = "gpu",
    mall: str | None = None,
    tag: str | None = None,
    recent: int = 10,
    failures: bool = False,
) -> DashboardFilter:
    return DashboardFilter(
        mall_id=mall,
        category=category or "gpu",
        tag=tag,
        recent=max(int(recent), 1),
        failures_only=failures,
    )


def redact_payload(payload: Any) -> Any:
    text = json.dumps(payload, ensure_ascii=False, default=str)
    redacted = redact_secrets(text, collect_secrets_for_redaction())
    return json.loads(redacted)
