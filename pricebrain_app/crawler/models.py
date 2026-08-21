"""Ingest listing payload — Crawler → POST /internal/ingest/listing (docs/07 §3, docs/08 input)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

REQUIRED_INGEST_FIELDS = (
    "product_id",
    "product_name",
    "mall_id",
    "product_url",
    "price",
    "seller",
    "crawled_at",
)


@dataclass(frozen=True)
class IngestListingPayload:
    product_id: str
    product_name: str
    mall_id: str
    product_url: str
    price: int
    seller: str
    crawled_at: datetime

    def __post_init__(self) -> None:
        validate_ingest_listing_payload(
            {
                "product_id": self.product_id,
                "product_name": self.product_name,
                "mall_id": self.mall_id,
                "product_url": self.product_url,
                "price": self.price,
                "seller": self.seller,
                "crawled_at": self.crawled_at,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        crawled_at = self.crawled_at
        if crawled_at.tzinfo is None:
            crawled_at = crawled_at.replace(tzinfo=timezone.utc)
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "mall_id": self.mall_id,
            "product_url": self.product_url,
            "price": int(self.price),
            "seller": self.seller,
            "crawled_at": crawled_at.isoformat(),
        }


def validate_ingest_listing_payload(data: dict[str, Any]) -> None:
    """Validate crawler → ingest payload before HTTP send."""
    for field in REQUIRED_INGEST_FIELDS:
        value = data.get(field)
        if value is None or value == "":
            raise ValueError(f"{field} is required")

    price = data["price"]
    if isinstance(price, bool) or not isinstance(price, int):
        raise ValueError("price must be a positive integer")
    if price <= 0:
        raise ValueError("price must be > 0")

    crawled_at = data["crawled_at"]
    if isinstance(crawled_at, datetime):
        return
    if isinstance(crawled_at, str) and crawled_at.strip():
        return
    raise ValueError("crawled_at must be a datetime or ISO-8601 string")


def utc_now_crawled_at() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_crawled_at(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    text = str(value).strip().replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def ingest_payload_from_raw(raw: dict[str, Any]) -> IngestListingPayload:
    """Map docs/07 RawProductData fields to ingest listing payload."""
    mall = str(raw.get("mall_id") or raw.get("mall") or "").strip()
    if not mall:
        raise ValueError("mall_id is required")

    product_id = raw.get("product_id")
    product_name = raw.get("product_name")
    product_url = raw.get("product_url")
    seller = raw.get("seller")
    price = raw.get("price")
    crawled_at = raw.get("crawled_at")

    if not product_id or not product_name:
        raise ValueError("product_id and product_name are required")
    if not product_url:
        raise ValueError("product_url is required")
    if not seller:
        raise ValueError("seller is required")
    if price is None:
        raise ValueError("price is required")
    if crawled_at is None:
        raise ValueError("crawled_at is required")

    if isinstance(price, bool) or not isinstance(price, int):
        raise ValueError("price must be a positive integer")

    return IngestListingPayload(
        product_id=str(product_id),
        product_name=str(product_name),
        mall_id=mall.lower(),
        product_url=str(product_url),
        price=int(price),
        seller=str(seller),
        crawled_at=_normalize_crawled_at(crawled_at),
    )
