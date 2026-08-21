"""Crawler operations view models — read-only observability DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pricebrain_app.crawler.results import CrawlerStatus


FAILED_CRAWLER_STATUSES = frozenset(
    {
        CrawlerStatus.HTTP_ERROR,
        CrawlerStatus.PARSE_ERROR,
        CrawlerStatus.TIMEOUT,
        CrawlerStatus.NETWORK_ERROR,
        CrawlerStatus.INGEST_ERROR,
        CrawlerStatus.VALIDATION_ERROR,
    }
)


@dataclass(frozen=True)
class TargetOperationalView:
    target_id: str
    mall_id: str
    product_url: str
    enabled: bool
    crawl_interval_seconds: int
    external_product_id: str | None
    product_name: str | None
    category: str | None
    tags: tuple[str, ...]
    priority: int
    crawl_status: str
    lease_owner: str | None
    lease_until: datetime | None
    last_crawled_at: datetime | None
    next_crawl_at: datetime | None
    last_status: str | None
    last_error_code: str | None
    last_error_message: str | None
    last_crawled_price: int | None
    created_at: datetime | None
    updated_at: datetime | None
    operational_state: str
    is_due: bool
    is_failed: bool
    has_active_lease: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "mall_id": self.mall_id,
            "product_url": self.product_url,
            "enabled": self.enabled,
            "crawl_interval_seconds": self.crawl_interval_seconds,
            "external_product_id": self.external_product_id,
            "product_name": self.product_name,
            "category": self.category,
            "tags": list(self.tags),
            "priority": self.priority,
            "crawl_status": self.crawl_status,
            "lease_owner": self.lease_owner,
            "lease_until": _iso(self.lease_until),
            "last_crawled_at": _iso(self.last_crawled_at),
            "next_crawl_at": _iso(self.next_crawl_at),
            "last_status": self.last_status,
            "last_error_code": self.last_error_code,
            "last_error_message": self.last_error_message,
            "last_crawled_price": self.last_crawled_price,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
            "operational_state": self.operational_state,
            "is_due": self.is_due,
            "is_failed": self.is_failed,
            "has_active_lease": self.has_active_lease,
        }


@dataclass(frozen=True)
class CrawlerOpsSummary:
    total_targets: int
    enabled_targets: int
    disabled_targets: int
    due_targets: int
    claimed_targets: int
    success_targets: int
    failed_targets: int
    lease_active_targets: int

    def to_dict(self) -> dict[str, int]:
        return {
            "total_targets": self.total_targets,
            "enabled_targets": self.enabled_targets,
            "disabled_targets": self.disabled_targets,
            "due_targets": self.due_targets,
            "claimed_targets": self.claimed_targets,
            "success_targets": self.success_targets,
            "failed_targets": self.failed_targets,
            "lease_active_targets": self.lease_active_targets,
        }


@dataclass(frozen=True)
class MallOpsSummary:
    mall_id: str
    total: int
    enabled: int
    disabled: int
    due: int
    success: int
    failed: int
    lease_active: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "mall_id": self.mall_id,
            "total": self.total,
            "enabled": self.enabled,
            "disabled": self.disabled,
            "due": self.due,
            "success": self.success,
            "failed": self.failed,
            "lease_active": self.lease_active,
        }


@dataclass(frozen=True)
class CrawlerFailureView:
    target_id: str
    mall_id: str
    product_url: str
    last_status: str | None
    last_error_code: str | None
    last_error_message: str | None
    last_crawled_at: datetime | None
    next_crawl_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "mall_id": self.mall_id,
            "product_url": self.product_url,
            "last_status": self.last_status,
            "last_error_code": self.last_error_code,
            "last_error_message": self.last_error_message,
            "last_crawled_at": _iso(self.last_crawled_at),
            "next_crawl_at": _iso(self.next_crawl_at),
        }


@dataclass(frozen=True)
class PriceChangeView:
    listing_id: str | None
    product_name: str | None
    current_price: int | None
    previous_price: int | None
    price_change: int | None
    last_crawled_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "product_name": self.product_name,
            "current_price": self.current_price,
            "previous_price": self.previous_price,
            "price_change": self.price_change,
            "last_crawled_at": _iso(self.last_crawled_at),
        }


@dataclass(frozen=True)
class ScheduleEntry:
    target_id: str
    mall_id: str
    next_crawl_at: datetime | None
    seconds_until_due: int | None
    is_due: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "mall_id": self.mall_id,
            "next_crawl_at": _iso(self.next_crawl_at),
            "seconds_until_due": self.seconds_until_due,
            "is_due": self.is_due,
        }


@dataclass
class WorkerHealthSnapshot:
    worker_enabled: bool = True
    last_cycle_started_at: datetime | None = None
    last_cycle_finished_at: datetime | None = None
    last_cycle_total: int = 0
    last_cycle_success: int = 0
    last_cycle_failed: int = 0
    last_cycle_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_enabled": self.worker_enabled,
            "last_cycle_started_at": _iso(self.last_cycle_started_at),
            "last_cycle_finished_at": _iso(self.last_cycle_finished_at),
            "last_cycle_total": self.last_cycle_total,
            "last_cycle_success": self.last_cycle_success,
            "last_cycle_failed": self.last_cycle_failed,
            "last_cycle_error": self.last_cycle_error,
        }


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        from pricebrain_app.crawler.targets import utc_now

        value = value.replace(tzinfo=utc_now().tzinfo)
    return value.isoformat()


def is_failed_last_status(status: str | None) -> bool:
    if not status:
        return False
    try:
        return CrawlerStatus(status) in FAILED_CRAWLER_STATUSES
    except ValueError:
        return False
