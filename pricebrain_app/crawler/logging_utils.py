"""Crawler logging helpers — safe URL formatting, no secrets in logs."""

from __future__ import annotations

import logging
import re
from urllib.parse import parse_qs, urlparse

LOGGER_NAME = "crawler.ssg"
SENSITIVE_QUERY_KEYS = frozenset(
    {
        "token",
        "access_token",
        "auth",
        "authorization",
        "api_key",
        "apikey",
        "key",
        "secret",
        "password",
        "session",
    }
)


def get_crawler_logger(name: str = LOGGER_NAME) -> logging.Logger:
    return logging.getLogger(name)


def safe_url_for_log(url: str | None) -> str:
    """Return a log-safe URL without sensitive query parameters."""
    if not url:
        return ""
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return url.strip()

    query = parse_qs(parsed.query, keep_blank_values=False)
    safe_parts: list[str] = []
    for key, values in query.items():
        if key.lower() in SENSITIVE_QUERY_KEYS:
            safe_parts.append(f"{key}=***")
        elif key.lower() == "itemid" and values:
            safe_parts.append(f"itemId={values[0]}")
        elif values:
            safe_parts.append(f"{key}=***")

    safe_query = "&".join(safe_parts)
    path = parsed.path or "/"
    if safe_query:
        return f"{parsed.scheme}://{parsed.netloc}{path}?{safe_query}"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def redact_secrets(text: str, secrets: list[str]) -> str:
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "***")
    redacted = re.sub(
        r"(Bearer\s+)[^\s\"']+",
        r"\1***",
        redacted,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(
        r"(api[_-]?key\s*[:=]\s*)[^\s\"',]+",
        r"\1***",
        redacted,
        flags=re.IGNORECASE,
    )
    return redacted
