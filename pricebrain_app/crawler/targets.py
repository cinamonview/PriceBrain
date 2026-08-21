"""Crawl target models — scheduler-managed crawl destinations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from pricebrain_app.crawler.malls.ssg import extract_ssg_item_id, validate_ssg_product_url

CRAWLER_TARGETS_COLLECTION = "crawler_targets"
DEFAULT_CRAWL_INTERVAL_SECONDS = 3600
DEFAULT_TARGET_PRIORITY = 50
CRAWL_STATUS_IDLE = "idle"
CRAWL_STATUS_CLAIMED = "claimed"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    text = str(value).strip().replace("Z", "+00:00")
    if not text:
        return None
    return datetime.fromisoformat(text)


@dataclass
class CrawlTarget:
    target_id: str
    mall_id: str
    product_url: str
    enabled: bool = True
    crawl_interval_seconds: int = DEFAULT_CRAWL_INTERVAL_SECONDS
    external_product_id: str | None = None
    product_name: str | None = None
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    priority: int = DEFAULT_TARGET_PRIORITY
    last_crawled_at: datetime | None = None
    next_crawl_at: datetime | None = None
    last_status: str | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    last_crawled_price: int | None = None
    crawl_status: str = CRAWL_STATUS_IDLE
    lease_until: datetime | None = None
    lease_owner: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def has_active_lease(self, now: datetime) -> bool:
        if self.lease_until is None:
            return False
        return self.lease_until > now

    def is_claimable(self, now: datetime, *, owner: str | None = None) -> bool:
        if not self.enabled:
            return False
        if self.next_crawl_at is not None and self.next_crawl_at > now:
            return False
        if not self.has_active_lease(now):
            return True
        return owner is not None and self.lease_owner == owner

    def to_firestore_dict(self) -> dict:
        return {
            "target_id": self.target_id,
            "mall_id": self.mall_id,
            "product_url": self.product_url,
            "enabled": self.enabled,
            "crawl_interval_seconds": int(self.crawl_interval_seconds),
            "external_product_id": self.external_product_id,
            "product_name": self.product_name,
            "category": self.category,
            "tags": list(self.tags),
            "priority": int(self.priority),
            "last_crawled_at": self.last_crawled_at,
            "next_crawl_at": self.next_crawl_at,
            "last_status": self.last_status,
            "last_error_code": self.last_error_code,
            "last_error_message": self.last_error_message,
            "last_crawled_price": self.last_crawled_price,
            "crawl_status": self.crawl_status,
            "lease_until": self.lease_until,
            "lease_owner": self.lease_owner,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_firestore_dict(cls, data: dict, *, doc_id: str | None = None) -> CrawlTarget:
        target_id = str(data.get("target_id") or doc_id or "")
        return cls(
            target_id=target_id,
            mall_id=str(data.get("mall_id") or ""),
            product_url=str(data.get("product_url") or ""),
            enabled=bool(data.get("enabled", True)),
            crawl_interval_seconds=int(
                data.get("crawl_interval_seconds", DEFAULT_CRAWL_INTERVAL_SECONDS)
            ),
            external_product_id=_optional_str(data.get("external_product_id")),
            product_name=_optional_str(data.get("product_name")),
            category=_optional_str(data.get("category")),
            tags=_parse_tags(data.get("tags")),
            priority=int(data.get("priority", DEFAULT_TARGET_PRIORITY)),
            last_crawled_at=parse_datetime(data.get("last_crawled_at")),
            next_crawl_at=parse_datetime(data.get("next_crawl_at")),
            last_status=data.get("last_status"),
            last_error_code=data.get("last_error_code"),
            last_error_message=data.get("last_error_message"),
            last_crawled_price=(
                int(data["last_crawled_price"])
                if data.get("last_crawled_price") is not None
                else None
            ),
            crawl_status=str(data.get("crawl_status") or CRAWL_STATUS_IDLE),
            lease_until=parse_datetime(data.get("lease_until")),
            lease_owner=data.get("lease_owner"),
            created_at=parse_datetime(data.get("created_at")),
            updated_at=parse_datetime(data.get("updated_at")),
        )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_tags(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        tags: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                tags.append(text)
        return tags
    return []


def derive_external_product_id(mall_id: str, product_url: str) -> str | None:
    """Derive a mall-specific external product ID from a validated product URL."""
    mall = mall_id.strip().lower()
    cleaned_url = validate_target_url(mall, product_url)
    if mall == "ssg":
        return extract_ssg_item_id(cleaned_url)
    return None


def validate_target_url(mall_id: str, url: str) -> str:
    """Validate a product URL for the given mall."""
    mall = mall_id.strip().lower()
    if mall == "ssg":
        return validate_ssg_product_url(url)
    raise ValueError(f"Unsupported mall for crawl target: {mall_id}")


def build_target_id(mall_id: str, product_url: str) -> str:
    """Build a stable crawl target ID from mall and product URL."""
    mall = mall_id.strip().lower()
    cleaned_url = validate_target_url(mall, product_url)
    if mall == "ssg":
        item_id = extract_ssg_item_id(cleaned_url)
        if item_id:
            return f"ssg_{item_id}"
    raise ValueError(f"Could not derive target_id for mall={mall_id}")
