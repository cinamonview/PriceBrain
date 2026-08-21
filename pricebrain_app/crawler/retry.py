"""Retry policy — docs/07 §14 (exponential backoff, limited retries)."""

from __future__ import annotations

RETRYABLE_HTTP_STATUS = frozenset({408, 429, 500, 502, 503, 504})
NON_RETRYABLE_HTTP_STATUS = frozenset({400, 401, 403, 404})


def should_retry_http_status(status_code: int) -> bool:
    if status_code in NON_RETRYABLE_HTTP_STATUS:
        return False
    if status_code in RETRYABLE_HTTP_STATUS:
        return True
    return status_code >= 500


def backoff_delay(attempt_index: int, delays: tuple[float, ...]) -> float:
    if attempt_index < len(delays):
        return delays[attempt_index]
    return delays[-1] if delays else 0.0
