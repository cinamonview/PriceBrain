"""Crawl target Firestore repository — crawler_targets collection only."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pricebrain_app.crawler.results import CrawlerResult, CrawlerStatus
from pricebrain_app.crawler.targets import (
    CRAWLER_TARGETS_COLLECTION,
    CRAWL_STATUS_CLAIMED,
    CRAWL_STATUS_IDLE,
    CrawlTarget,
    build_target_id,
    derive_external_product_id,
    parse_datetime,
    utc_now,
    validate_target_url,
)


class CrawlTargetRepository:
    """Persist crawl targets — no crawler execution logic."""

    def __init__(self, db: Any) -> None:
        self._db = db

    def get(self, target_id: str) -> CrawlTarget | None:
        doc = self._db.collection(CRAWLER_TARGETS_COLLECTION).document(target_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict() or {}
        return CrawlTarget.from_firestore_dict(data, doc_id=doc.id)

    def upsert(
        self,
        *,
        mall_id: str,
        product_url: str,
        enabled: bool = True,
        crawl_interval_seconds: int | None = None,
        now: datetime | None = None,
    ) -> CrawlTarget:
        cleaned_url = validate_target_url(mall_id, product_url)
        target_id = build_target_id(mall_id, cleaned_url)
        current = self.get(target_id)
        run_at = now or utc_now()

        payload: dict[str, Any] = {
            "target_id": target_id,
            "mall_id": mall_id.strip().lower(),
            "product_url": cleaned_url,
            "enabled": enabled,
            "updated_at": run_at,
        }
        if crawl_interval_seconds is not None:
            payload["crawl_interval_seconds"] = int(crawl_interval_seconds)

        if current is None:
            payload["created_at"] = run_at
            payload["next_crawl_at"] = run_at
        elif current.next_crawl_at is None:
            payload["next_crawl_at"] = run_at

        self._db.collection(CRAWLER_TARGETS_COLLECTION).document(target_id).set(
            payload,
            merge=True,
        )
        saved = self.get(target_id)
        if saved is None:
            raise RuntimeError(f"Failed to upsert crawl target: {target_id}")
        return saved

    def merge_catalog(
        self,
        *,
        mall_id: str,
        product_url: str,
        enabled: bool = True,
        crawl_interval_seconds: int | None = None,
        product_name: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        priority: int | None = None,
        external_product_id: str | None = None,
        now: datetime | None = None,
    ) -> tuple[CrawlTarget, bool]:
        """Register or update catalog metadata without touching operational crawl state."""
        cleaned_url = validate_target_url(mall_id, product_url)
        target_id = build_target_id(mall_id, cleaned_url)
        current = self.get(target_id)
        run_at = now or utc_now()
        normalized_mall = mall_id.strip().lower()
        derived_external_id = external_product_id or derive_external_product_id(
            normalized_mall,
            cleaned_url,
        )
        normalized_category = category.strip().lower() if category else None
        normalized_tags = [item.strip() for item in (tags or []) if item.strip()]
        normalized_priority = int(priority) if priority is not None else None

        payload: dict[str, Any] = {
            "target_id": target_id,
            "mall_id": normalized_mall,
            "product_url": cleaned_url,
            "enabled": enabled,
            "external_product_id": derived_external_id,
            "product_name": product_name,
            "category": normalized_category,
            "tags": normalized_tags,
            "updated_at": run_at,
        }
        if crawl_interval_seconds is not None:
            payload["crawl_interval_seconds"] = int(crawl_interval_seconds)
        if normalized_priority is not None:
            payload["priority"] = normalized_priority

        created = current is None
        if created:
            payload["created_at"] = run_at
            payload["next_crawl_at"] = run_at
        elif current.next_crawl_at is None:
            payload["next_crawl_at"] = run_at

        self._db.collection(CRAWLER_TARGETS_COLLECTION).document(target_id).set(
            payload,
            merge=True,
        )
        saved = self.get(target_id)
        if saved is None:
            raise RuntimeError(f"Failed to merge crawl target catalog entry: {target_id}")
        return saved, created

    def bulk_set_enabled(
        self,
        *,
        enabled: bool,
        mall_id: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        now: datetime | None = None,
    ) -> int:
        """Enable or disable targets matching filters — configuration only."""
        run_at = now or utc_now()
        updated = 0
        for target in self.list_all(mall_id=mall_id, category=category, tag=tag):
            if target.enabled == enabled:
                continue
            self._db.collection(CRAWLER_TARGETS_COLLECTION).document(target.target_id).set(
                {"enabled": enabled, "updated_at": run_at},
                merge=True,
            )
            updated += 1
        return updated

    def list_enabled(
        self,
        *,
        mall_id: str | None = None,
    ) -> list[CrawlTarget]:
        return self.list_all(mall_id=mall_id, enabled=True)

    def list_all(
        self,
        *,
        mall_id: str | None = None,
        enabled: bool | None = None,
        category: str | None = None,
        tag: str | None = None,
    ) -> list[CrawlTarget]:
        targets: list[CrawlTarget] = []
        for doc in self._db.collection(CRAWLER_TARGETS_COLLECTION).stream():
            data = doc.to_dict() or {}
            target = CrawlTarget.from_firestore_dict(data, doc_id=doc.id)
            if enabled is not None and target.enabled != enabled:
                continue
            if mall_id is not None and target.mall_id != mall_id.strip().lower():
                continue
            if category is not None and target.category != category.strip().lower():
                continue
            if tag is not None and tag.strip().lower() not in {
                item.lower() for item in target.tags
            }:
                continue
            targets.append(target)
        return sorted(targets, key=lambda item: (-item.priority, item.target_id))

    def list_due(
        self,
        now: datetime,
        *,
        mall_id: str | None = None,
        target_id: str | None = None,
    ) -> list[CrawlTarget]:
        if target_id is not None:
            target = self.get(target_id)
            if target is None or not target.enabled:
                return []
            if mall_id is not None and target.mall_id != mall_id.strip().lower():
                return []
            if target.next_crawl_at is not None and target.next_crawl_at > now:
                return []
            return [target]

        due: list[CrawlTarget] = []
        for target in self.list_enabled(mall_id=mall_id):
            if target.next_crawl_at is None or target.next_crawl_at <= now:
                due.append(target)
        return sorted(due, key=lambda item: (-item.priority, item.target_id))

    def try_claim(
        self,
        target_id: str,
        owner: str,
        now: datetime,
        lease_seconds: int,
    ) -> CrawlTarget | None:
        """Acquire a short-lived lease for a due target, or return None if unavailable."""
        target = self.get(target_id)
        if target is None or not target.is_claimable(now, owner=owner):
            return None

        lease_until = now + timedelta(seconds=max(int(lease_seconds), 1))
        payload: dict[str, Any] = {
            "crawl_status": CRAWL_STATUS_CLAIMED,
            "lease_until": lease_until,
            "lease_owner": owner,
            "updated_at": now,
        }
        self._db.collection(CRAWLER_TARGETS_COLLECTION).document(target_id).set(
            payload,
            merge=True,
        )
        claimed = self.get(target_id)
        if claimed is None or not claimed.is_claimable(now, owner=owner):
            return None
        return claimed

    def release_lease(self, target_id: str, owner: str, *, now: datetime | None = None) -> bool:
        """Release a lease held by owner; no-op if not held by owner."""
        target = self.get(target_id)
        if target is None:
            return False
        if target.lease_owner and target.lease_owner != owner:
            return False
        if target.crawl_status == CRAWL_STATUS_IDLE and target.lease_until is None:
            return True

        run_at = now or utc_now()
        payload: dict[str, Any] = {
            "crawl_status": CRAWL_STATUS_IDLE,
            "lease_until": None,
            "lease_owner": None,
            "updated_at": run_at,
        }
        self._db.collection(CRAWLER_TARGETS_COLLECTION).document(target_id).set(
            payload,
            merge=True,
        )
        return True

    def update_after_crawl(
        self,
        target_id: str,
        *,
        result: CrawlerResult,
        next_crawl_at: datetime,
        crawled_at: datetime | None = None,
    ) -> CrawlTarget:
        run_at = crawled_at or parse_datetime(result.crawled_at) or utc_now()
        error_code = _result_error_code(result)
        last_price = result.payload.price if result.payload is not None else None

        update_payload: dict[str, Any] = {
            "last_crawled_at": run_at,
            "next_crawl_at": next_crawl_at,
            "last_status": result.status.value,
            "last_error_code": error_code,
            "last_error_message": result.message or None,
            "last_crawled_price": last_price,
            "crawl_status": CRAWL_STATUS_IDLE,
            "lease_until": None,
            "lease_owner": None,
            "updated_at": utc_now(),
        }
        self._db.collection(CRAWLER_TARGETS_COLLECTION).document(target_id).set(
            update_payload,
            merge=True,
        )
        saved = self.get(target_id)
        if saved is None:
            raise RuntimeError(f"Crawl target not found after update: {target_id}")
        return saved


def _result_error_code(result: CrawlerResult) -> str | None:
    if result.status == CrawlerStatus.SUCCESS:
        return None
    if result.message in {"SSG_ACCESS_DENIED", "ACCESS_DENIED", "NOT_FOUND"}:
        return result.message
    return result.status.value
