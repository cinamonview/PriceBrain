"""Pending (unapproved) GPU model repository — Collection: pending_gpu_models.

Quarantine area for gpu_model_id values the parser produced but GPU master does not
contain. Kept strictly separate from gpu_models: nothing here is ever promoted to
master automatically.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pricebrain_app.repository import constants as c
from pricebrain_app.repository.base import BaseRepository

PENDING_STATUS_REVIEW = "PENDING_REVIEW"
PENDING_STATUS_APPROVED = "APPROVED"
PENDING_STATUS_REJECTED = "REJECTED"

DETECTED_BY_GPU_PARSER = "pipeline.gpu_parser"

# Examples are evidence for a human reviewer, not an archive. Capped so a
# Search Batch discovering the same model thousands of times cannot grow the
# document past Firestore's 1MiB limit.
MAX_EXAMPLES = 5


def _append_capped(existing: Any, value: str | None) -> list[str]:
    items = [str(item) for item in existing] if isinstance(existing, list) else []
    if not value or value in items or len(items) >= MAX_EXAMPLES:
        return items
    items.append(value)
    return items


def _merge_sorted(existing: Any, value: str | None) -> list[str]:
    items = {str(item) for item in existing} if isinstance(existing, list) else set()
    if value:
        items.add(value)
    return sorted(items)


class PendingGpuModelRepository(BaseRepository):
    """Aggregate one document per canonical unknown slug (read-modify-write).

    Follows the project's existing non-transactional upsert pattern (see
    ProductRepository.upsert_product); the repository has no transaction or
    Increment/ArrayUnion usage anywhere.
    """

    def get(self, gpu_model_id: str) -> dict[str, Any] | None:
        doc = self.db.collection(c.PENDING_GPU_MODELS).document(gpu_model_id).get()
        return doc.to_dict() if doc.exists else None

    def record_unknown_model(
        self,
        *,
        gpu_model_id: str,
        display_name: str | None = None,
        gpu_series: str | None = None,
        mall_id: str | None = None,
        product_name: str | None = None,
        product_url: str | None = None,
        detected_by: str = DETECTED_BY_GPU_PARSER,
        seen_at: datetime | None = None,
    ) -> str:
        """Upsert the quarantine document for one unknown-model sighting."""
        if not gpu_model_id:
            raise ValueError("gpu_model_id is required to quarantine an unknown model")

        now = seen_at or datetime.now(timezone.utc)
        ref = self.db.collection(c.PENDING_GPU_MODELS).document(gpu_model_id)
        current = ref.get()
        existing = current.to_dict() if current.exists else None

        payload: dict[str, Any] = {
            "gpu_model_id": gpu_model_id,
            "detected_by": detected_by,
            "last_seen_at": now,
            "seen_count": int((existing or {}).get("seen_count", 0)) + 1,
            "source_malls": _merge_sorted((existing or {}).get("source_malls"), mall_id),
            "example_product_names": _append_capped(
                (existing or {}).get("example_product_names"), product_name
            ),
            "example_product_urls": _append_capped(
                (existing or {}).get("example_product_urls"), product_url
            ),
        }
        if display_name:
            payload["display_name"] = display_name
        if gpu_series:
            payload["gpu_series"] = gpu_series

        if existing is None:
            payload["first_seen_at"] = now
            # vendor_id/family_id stay unset: the parser cannot derive them and
            # master reference data must not be inferred (see docs/05 §3.3).
            payload["status"] = PENDING_STATUS_REVIEW

        # An existing status is a reviewer decision and must survive re-sightings.
        ref.set(payload, merge=True)
        return gpu_model_id
