"""Crawl target catalog seeding and bulk configuration management."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.targets import DEFAULT_CRAWL_INTERVAL_SECONDS, DEFAULT_TARGET_PRIORITY


@dataclass(frozen=True)
class CatalogEntry:
    mall_id: str
    product_url: str
    product_name: str | None = None
    category: str | None = None
    tags: tuple[str, ...] = ()
    crawl_interval_seconds: int = DEFAULT_CRAWL_INTERVAL_SECONDS
    enabled: bool = True
    priority: int = DEFAULT_TARGET_PRIORITY
    external_product_id: str | None = None


@dataclass
class SeedResult:
    created: int = 0
    updated: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.created + self.updated


@dataclass(frozen=True)
class BulkUpdateFilter:
    mall_id: str | None = None
    category: str | None = None
    tag: str | None = None


def parse_catalog_entry(raw: dict[str, Any]) -> CatalogEntry:
    mall_id = str(raw.get("mall_id") or "").strip()
    product_url = str(raw.get("product_url") or "").strip()
    if not mall_id:
        raise ValueError("mall_id is required")
    if not product_url:
        raise ValueError("product_url is required")

    tags_raw = raw.get("tags")
    tags: tuple[str, ...]
    if tags_raw is None:
        tags = ()
    elif isinstance(tags_raw, list):
        tags = tuple(str(item).strip() for item in tags_raw if str(item).strip())
    else:
        text = str(tags_raw).strip()
        tags = (text,) if text else ()

    interval_raw = raw.get("crawl_interval_seconds", DEFAULT_CRAWL_INTERVAL_SECONDS)
    priority_raw = raw.get("priority", DEFAULT_TARGET_PRIORITY)
    enabled_raw = raw.get("enabled", True)

    return CatalogEntry(
        mall_id=mall_id,
        product_url=product_url,
        product_name=_optional_text(raw.get("product_name")),
        category=_optional_text(raw.get("category")),
        tags=tags,
        crawl_interval_seconds=int(interval_raw),
        enabled=bool(enabled_raw),
        priority=int(priority_raw),
        external_product_id=_optional_text(raw.get("external_product_id")),
    )


def load_catalog_entries_from_file(path: str | Path) -> list[CatalogEntry]:
    file_path = Path(path)
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Catalog file must contain a JSON array")
    return [parse_catalog_entry(item) for item in payload]


def seed_catalog_entries(
    repository: CrawlTargetRepository,
    entries: list[CatalogEntry],
    *,
    now: datetime | None = None,
) -> SeedResult:
    result = SeedResult()
    for entry in entries:
        try:
            _, created = repository.merge_catalog(
                mall_id=entry.mall_id,
                product_url=entry.product_url,
                enabled=entry.enabled,
                crawl_interval_seconds=entry.crawl_interval_seconds,
                product_name=entry.product_name,
                category=entry.category,
                tags=list(entry.tags),
                priority=entry.priority,
                external_product_id=entry.external_product_id,
                now=now,
            )
        except ValueError as exc:
            result.errors.append(f"{entry.product_url}: {exc}")
            continue
        if created:
            result.created += 1
        else:
            result.updated += 1
    return result


def bulk_set_enabled(
    repository: CrawlTargetRepository,
    *,
    enabled: bool,
    filters: BulkUpdateFilter | None = None,
    now: datetime | None = None,
) -> int:
    flt = filters or BulkUpdateFilter()
    return repository.bulk_set_enabled(
        enabled=enabled,
        mall_id=flt.mall_id,
        category=flt.category,
        tag=flt.tag,
        now=now,
    )


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
