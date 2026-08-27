"""Shared text/URL/price helpers — docs/08 §5–§11."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pricebrain_app.pipeline.constants import MALL_CODE_MAP, URL_TRACKING_QUERY_PARAMS


def clean_string(value: str | None) -> str | None:
    if value is None:
        return None
    text = html.unescape(str(value)).strip()
    if not text:
        return None
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_price(value: Any) -> int | None:
    """Integer KRW price — docs/08 §7."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        return int(value) if value > 0 else None
    digits = re.sub(r"[^0-9]", "", str(value))
    if not digits:
        return None
    price = int(digits)
    return price if price > 0 else None


def normalize_mall_code(mall: str | None) -> str | None:
    """Uppercase mall code — used for listing document IDs and `malls/{code}`."""
    if not mall:
        return None
    key = mall.strip()
    return MALL_CODE_MAP.get(key, MALL_CODE_MAP.get(key.upper(), key.upper()))


def normalize_mall_id(mall: str | None) -> str | None:
    """Canonical lowercase mall_id — used for crawl targets, API params and filters."""
    code = normalize_mall_code(mall)
    return code.lower() if code else None


def normalize_product_url(url: str | None) -> str | None:
    """Strip tracking query params — docs/08 §10."""
    if not url:
        return None
    text = url.strip()
    if text.startswith("//"):
        text = f"https:{text}"
    parsed = urlparse(text)
    if not parsed.scheme:
        text = f"https://{text.lstrip('/')}"
        parsed = urlparse(text)
    kept = [
        (key, val)
        for key, val in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in URL_TRACKING_QUERY_PARAMS
    ]
    normalized = parsed._replace(query=urlencode(kept))
    return urlunparse(normalized)


def normalize_image_url(url: str | None) -> str | None:
    if not url:
        return None
    text = url.strip()
    if text.startswith("//"):
        return f"https:{text}"
    return text


def normalize_seller_name(seller: str | None) -> str | None:
    if not seller:
        return None
    return re.sub(r"\s+", "", seller.strip())


def seller_slug(seller: str) -> str:
    """Build seller slug for seller_id — docs/05 §2 sellers."""
    ascii_part = re.sub(r"[^A-Za-z0-9]", "", seller).upper()
    if ascii_part:
        return ascii_part[:32]
    digest = hashlib.sha1(seller.encode("utf-8")).hexdigest()[:12]
    return digest.upper()


def parse_crawled_at(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        text = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


def gpu_model_to_slug(gpu_model: str) -> str:
    """docs/05 §3.3 slug example: rtx_5080."""
    slug = gpu_model.strip().lower()
    slug = re.sub(r"\s+", "_", slug)
    slug = re.sub(r"[^a-z0-9_]", "", slug)
    return slug
