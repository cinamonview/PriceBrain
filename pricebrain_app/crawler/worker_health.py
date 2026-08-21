"""Process-local worker health snapshot for operations visibility."""

from __future__ import annotations

from datetime import datetime
from threading import Lock

from pricebrain_app.crawler.ops_models import WorkerHealthSnapshot
from pricebrain_app.crawler.results import CrawlerBatchSummary
from pricebrain_app.crawler.targets import utc_now

_lock = Lock()
_health = WorkerHealthSnapshot()


def get_worker_health() -> WorkerHealthSnapshot:
    with _lock:
        return WorkerHealthSnapshot(**_health.to_dict())


def reset_worker_health() -> None:
    global _health
    with _lock:
        _health = WorkerHealthSnapshot()


def mark_cycle_started(*, worker_enabled: bool) -> None:
    with _lock:
        _health.worker_enabled = worker_enabled
        _health.last_cycle_started_at = utc_now()
        _health.last_cycle_error = None


def mark_cycle_finished(summary: CrawlerBatchSummary, *, error: str | None = None) -> None:
    with _lock:
        _health.last_cycle_finished_at = utc_now()
        _health.last_cycle_total = summary.total
        _health.last_cycle_success = summary.success
        _health.last_cycle_failed = (
            summary.http_error
            + summary.timeout
            + summary.network_error
            + summary.parse_error
            + summary.validation_error
            + summary.ingest_error
        )
        _health.last_cycle_error = error
