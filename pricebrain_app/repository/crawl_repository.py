"""Crawl job/log repository — docs/05 §3.10–§3.11, docs/09 §6."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pricebrain_app.repository import constants as c
from pricebrain_app.repository.base import BaseRepository

CRAWL_STATUS_PENDING = "PENDING"
CRAWL_STATUS_RUNNING = "RUNNING"
CRAWL_STATUS_COMPLETED = "COMPLETED"
CRAWL_STATUS_FAILED = "FAILED"

LOG_LEVEL_INFO = "INFO"
LOG_LEVEL_WARN = "WARN"
LOG_LEVEL_ERROR = "ERROR"


def build_crawl_job_id(mall_id: str, started_at: datetime) -> str:
    """Document ID rule: {mall_code}_{timestamp} — docs/05 §2."""
    return f"{mall_id}_{started_at.strftime('%Y%m%d_%H%M%S')}"


class CrawlRepository(BaseRepository):
    def start_job(
        self,
        mall_id: str,
        *,
        keyword: str | None = None,
        started_at: datetime | None = None,
    ) -> str:
        """Create crawl_jobs document with RUNNING status."""
        started = started_at or datetime.now(timezone.utc)
        job_id = build_crawl_job_id(mall_id, started)
        payload: dict[str, Any] = {
            "job_id": job_id,
            "mall_id": mall_id,
            "status": CRAWL_STATUS_RUNNING,
            "started_at": started,
        }
        if keyword:
            payload["keyword"] = keyword
        self.db.collection(c.CRAWL_JOBS).document(job_id).set(payload)
        return job_id

    def complete_job(
        self,
        job_id: str,
        *,
        completed_at: datetime | None = None,
    ) -> None:
        """Mark crawl job COMPLETED."""
        finished = completed_at or datetime.now(timezone.utc)
        self.db.collection(c.CRAWL_JOBS).document(job_id).set(
            {
                "status": CRAWL_STATUS_COMPLETED,
                "completed_at": finished,
            },
            merge=True,
        )

    def fail_job(
        self,
        job_id: str,
        error_message: str,
        *,
        completed_at: datetime | None = None,
    ) -> None:
        """Mark crawl job FAILED."""
        finished = completed_at or datetime.now(timezone.utc)
        self.db.collection(c.CRAWL_JOBS).document(job_id).set(
            {
                "status": CRAWL_STATUS_FAILED,
                "completed_at": finished,
                "error_message": error_message,
            },
            merge=True,
        )

    def create_log(
        self,
        job_id: str,
        mall_id: str,
        level: str,
        message: str,
        *,
        created_at: datetime | None = None,
    ) -> str:
        """Append crawl_logs document (auto log_id) — docs/05 §3.11."""
        created = created_at or datetime.now(timezone.utc)
        ref = self.db.collection(c.CRAWL_LOGS).document()
        log_id = ref.id
        ref.set(
            {
                "log_id": log_id,
                "job_id": job_id,
                "mall_id": mall_id,
                "level": level,
                "message": message,
                "created_at": created,
            }
        )
        return log_id

    def create_job(self, job_id: str, data: dict[str, Any]) -> str:
        payload = dict(data)
        payload.setdefault("job_id", job_id)
        self.db.collection(c.CRAWL_JOBS).document(job_id).set(payload, merge=True)
        return job_id

    def log(self, log_id: str, data: dict[str, Any]) -> str:
        """Legacy explicit log_id write — prefer create_log()."""
        payload = dict(data)
        payload.setdefault("log_id", log_id)
        self.db.collection(c.CRAWL_LOGS).document(log_id).set(payload, merge=True)
        return log_id
