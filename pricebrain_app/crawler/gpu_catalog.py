"""GPU catalog input model and validation — maps to crawl target catalog fields."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pricebrain_app.crawler.targets import (
    DEFAULT_CRAWL_INTERVAL_SECONDS,
    DEFAULT_TARGET_PRIORITY,
    validate_target_url,
)

SUPPORTED_MALL_IDS = frozenset({"ssg"})
MIN_CATALOG_PRIORITY = 1
MAX_CATALOG_PRIORITY = 1000
EXTERNAL_PRODUCT_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


@dataclass(frozen=True)
class GpuCatalogItem:
    mall_id: str
    product_url: str
    product_name: str | None = None
    brand: str | None = None
    category: str | None = None
    tags: tuple[str, ...] = ()
    external_product_id: str | None = None
    enabled: bool = True
    priority: int = DEFAULT_TARGET_PRIORITY
    crawl_interval_seconds: int = DEFAULT_CRAWL_INTERVAL_SECONDS

    def to_catalog_entry(self) -> CatalogEntry:
        from pricebrain_app.crawler.target_management import CatalogEntry

        tags = list(self.tags)
        if self.brand:
            brand_tag = self.brand.strip().lower()
            if brand_tag and brand_tag not in {item.lower() for item in tags}:
                tags.insert(0, brand_tag)
        return CatalogEntry(
            mall_id=self.mall_id,
            product_url=self.product_url,
            product_name=self.product_name,
            category=self.category,
            tags=tuple(tags),
            crawl_interval_seconds=self.crawl_interval_seconds,
            enabled=self.enabled,
            priority=self.priority,
            external_product_id=self.external_product_id,
        )


@dataclass(frozen=True)
class CatalogValidationError:
    index: int
    product_url: str
    message: str


def load_gpu_catalog_file(path: str | Path) -> tuple[list[GpuCatalogItem], list[CatalogValidationError]]:
    file_path = Path(path)
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Catalog file must contain a JSON array")

    items: list[GpuCatalogItem] = []
    errors: list[CatalogValidationError] = []
    for index, raw in enumerate(payload):
        if not isinstance(raw, dict):
            errors.append(
                CatalogValidationError(
                    index=index,
                    product_url="",
                    message="Catalog entry must be a JSON object",
                )
            )
            continue
        try:
            items.append(parse_gpu_catalog_item(raw))
        except ValueError as exc:
            product_url = str(raw.get("product_url") or "")
            errors.append(
                CatalogValidationError(
                    index=index,
                    product_url=product_url,
                    message=str(exc),
                )
            )
    return items, errors


def parse_gpu_catalog_item(raw: dict[str, Any]) -> GpuCatalogItem:
    mall_id = str(raw.get("mall_id") or "").strip().lower()
    product_url = str(raw.get("product_url") or "").strip()
    if not mall_id:
        raise ValueError("mall_id is required")
    if mall_id not in SUPPORTED_MALL_IDS:
        raise ValueError(f"Unsupported mall_id: {mall_id}")
    if not product_url:
        raise ValueError("product_url is required")
    _validate_url_format(product_url)
    validate_target_url(mall_id, product_url)

    enabled = _parse_enabled(raw.get("enabled", True))
    priority = _parse_priority(raw.get("priority", DEFAULT_TARGET_PRIORITY))
    tags = _parse_tags(raw.get("tags"))
    external_product_id = _parse_external_product_id(raw.get("external_product_id"))
    crawl_interval_seconds = _parse_crawl_interval(raw.get("crawl_interval_seconds"))

    return GpuCatalogItem(
        mall_id=mall_id,
        product_url=product_url,
        product_name=_optional_text(raw.get("product_name")),
        brand=_optional_text(raw.get("brand")),
        category=_normalize_category(raw.get("category")),
        tags=tags,
        external_product_id=external_product_id,
        enabled=enabled,
        priority=priority,
        crawl_interval_seconds=crawl_interval_seconds,
    )


def gpu_model_label_from_target(*, product_name: str | None, tags: list[str]) -> str:
    for tag in tags:
        if tag.lower().startswith("rtx"):
            return format_rtx_tag(tag)
    if product_name:
        match = re.search(r"(RTX\s*\d+(?:\s*Ti|\s*Super)?)", product_name, re.IGNORECASE)
        if match:
            return " ".join(match.group(1).upper().split())
    return "Other"


def format_rtx_tag(tag: str) -> str:
    normalized = tag.lower().replace(" ", "")
    if not normalized.startswith("rtx"):
        return tag
    body = normalized[3:]
    if body.endswith("ti"):
        return f"RTX {body[:-2]} Ti"
    if body.endswith("super"):
        return f"RTX {body[:-5]} Super"
    return f"RTX {body}"


def _validate_url_format(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid product URL scheme: {url}")
    if not parsed.netloc:
        raise ValueError(f"Invalid product URL: {url}")


def _parse_enabled(value: object) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError("enabled must be a boolean")


def _parse_priority(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("priority must be an integer")
    if value < MIN_CATALOG_PRIORITY or value > MAX_CATALOG_PRIORITY:
        raise ValueError(
            f"priority must be between {MIN_CATALOG_PRIORITY} and {MAX_CATALOG_PRIORITY}"
        )
    return value


def _parse_crawl_interval(value: object) -> int:
    if value is None:
        return DEFAULT_CRAWL_INTERVAL_SECONDS
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("crawl_interval_seconds must be an integer")
    if value < 1:
        raise ValueError("crawl_interval_seconds must be at least 1")
    return value


def _parse_tags(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("tags must be an array of strings")
    tags: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("tags must be an array of strings")
        text = item.strip()
        if text:
            tags.append(text)
    return tuple(tags)


def _parse_external_product_id(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if not EXTERNAL_PRODUCT_ID_PATTERN.match(text):
        raise ValueError("external_product_id contains invalid characters")
    return text


def _normalize_category(value: object) -> str | None:
    text = _optional_text(value)
    return text.lower() if text else None


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
