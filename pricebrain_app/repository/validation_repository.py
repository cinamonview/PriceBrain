"""Validation log repository — docs/05 §3.12, docs/09 §6."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pricebrain_app.repository import constants as c
from pricebrain_app.repository.base import BaseRepository

VALIDATION_STATUS_PASS = "PASS"
VALIDATION_STATUS_FAIL = "FAIL"


class ValidationRepository(BaseRepository):
    def log_validation(
        self,
        source: str,
        status: str,
        details: dict[str, Any] | None = None,
        *,
        created_at: datetime | None = None,
    ) -> str:
        """Persist validation_logs document (auto log_id)."""
        created = created_at or datetime.now(timezone.utc)
        ref = self.db.collection(c.VALIDATION_LOGS).document()
        log_id = ref.id
        payload: dict[str, Any] = {
            "log_id": log_id,
            "source": source,
            "status": status,
            "created_at": created,
        }
        if details:
            payload["details"] = details
        ref.set(payload)
        return log_id

    def log_validation_failure(
        self,
        source: str,
        details: dict[str, Any],
        *,
        created_at: datetime | None = None,
    ) -> str:
        return self.log_validation(
            source,
            VALIDATION_STATUS_FAIL,
            details,
            created_at=created_at,
        )
