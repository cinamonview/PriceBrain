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
    total: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    invalid: int = 0
    errors: list[str] = field(default_factory=list)
    previews: list[SeedPreview] = field(default_factory=list)

    def finalize(self) -> SeedResult:
        self.total = self.created + self.updated + self.skipped + self.invalid
        return self

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "total": self.total,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "invalid": self.invalid,
        }
        if self.errors:
            payload["errors"] = self.errors
        if self.previews:
            payload["previews"] = [preview.to_dict() for preview in self.previews]
        return payload


@dataclass(frozen=True)
class SeedPreview:
    target_id: str
    action: str
    product_url: str
    changes: tuple[tuple[str, Any, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "action": self.action,
            "product_url": self.product_url,
            "changes": [
                {"field": field, "current": current, "planned": planned}
                for field, current, planned in self.changes
            ],
        }


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
    from pricebrain_app.crawler.gpu_catalog import load_gpu_catalog_file

    items, errors = load_gpu_catalog_file(path)
    if errors:
        messages = [f"{item.product_url or 'entry'}: {item.message}" for item in errors]
        raise ValueError("; ".join(messages))
    return [item.to_catalog_entry() for item in items]


def seed_catalog_entries(
    repository: CrawlTargetRepository,
    entries: list[CatalogEntry],
    *,
    now: datetime | None = None,
    dry_run: bool = False,
) -> SeedResult:
    result = SeedResult()
    for entry in entries:
        try:
            preview = repository.preview_catalog_merge(
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
            result.invalid += 1
            result.errors.append(f"{entry.product_url}: {exc}")
            continue

        result.previews.append(preview)
        if dry_run:
            if preview.action == "create":
                result.created += 1
            elif preview.action == "update":
                result.updated += 1
            else:
                result.skipped += 1
            continue

        if preview.action == "skip":
            result.skipped += 1
            continue

        _, action = repository.merge_catalog(
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
        if action == "create":
            result.created += 1
        else:
            result.updated += 1
    return result.finalize()


def seed_gpu_catalog_file(
    repository: CrawlTargetRepository,
    path: str | Path,
    *,
    now: datetime | None = None,
    dry_run: bool = False,
) -> SeedResult:
    from pricebrain_app.crawler.gpu_catalog import load_gpu_catalog_file

    items, validation_errors = load_gpu_catalog_file(path)
    result = SeedResult()
    for error in validation_errors:
        result.invalid += 1
        label = error.product_url or f"index={error.index}"
        result.errors.append(f"{label}: {error.message}")

    if items:
        item_result = seed_catalog_entries(
            repository,
            [item.to_catalog_entry() for item in items],
            now=now,
            dry_run=dry_run,
        )
        result.created += item_result.created
        result.updated += item_result.updated
        result.skipped += item_result.skipped
        result.previews.extend(item_result.previews)
    return result.finalize()


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
