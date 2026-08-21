"""Crawler worker — continuous or one-shot operational execution with lease safety."""

from __future__ import annotations

import os
import signal
import socket
import time
import uuid
from dataclasses import dataclass
from typing import Callable

from pricebrain_app.crawler.client import IngestClient
from pricebrain_app.crawler.config import WorkerConfig, get_worker_config
from pricebrain_app.crawler.logging_utils import get_crawler_logger
from pricebrain_app.crawler.metrics import record_lease_claim, record_lease_skip
from pricebrain_app.crawler.observability_events import log_observability_event
from pricebrain_app.crawler.results import CrawlerBatchSummary, CrawlerResult
from pricebrain_app.crawler.scheduler import CrawlerScheduler, SchedulerRunResult
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.targets import CrawlTarget, utc_now
from pricebrain_app.crawler.worker_health import mark_cycle_finished, mark_cycle_started

logger = get_crawler_logger("crawler.worker")


@dataclass(frozen=True)
class WorkerRunResult:
    claimed_targets: list[CrawlTarget]
    skipped_targets: int
    run: SchedulerRunResult
    shutdown_requested: bool = False

    @property
    def summary(self) -> CrawlerBatchSummary:
        return self.run.summary

    @property
    def results(self) -> list[CrawlerResult]:
        return self.run.results


class GracefulShutdown:
    """Handle SIGINT/SIGTERM for cooperative worker shutdown."""

    def __init__(self) -> None:
        self._stop = False
        self._previous_handlers: dict[int, Callable | int | None] = {}

    @property
    def should_stop(self) -> bool:
        return self._stop

    def request_stop(self) -> None:
        if not self._stop:
            logger.info("graceful shutdown")
        self._stop = True

    def register(self) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                self._previous_handlers[sig] = signal.getsignal(sig)
                signal.signal(sig, self._handle_signal)
            except (AttributeError, ValueError, OSError):
                continue

    def restore(self) -> None:
        for sig, previous in self._previous_handlers.items():
            try:
                signal.signal(sig, previous)
            except (AttributeError, ValueError, OSError):
                continue
        self._previous_handlers.clear()

    def _handle_signal(self, signum: int, _frame: object) -> None:
        logger.info("graceful shutdown", extra={"signal": signum})
        self.request_stop()


def generate_worker_owner_id() -> str:
    host = socket.gethostname()
    return f"{host}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


class CrawlerWorker:
    """Operational runner that claims due targets and delegates crawl work to Scheduler."""

    def __init__(
        self,
        target_repository: CrawlTargetRepository,
        scheduler: CrawlerScheduler,
        *,
        owner_id: str | None = None,
        config: WorkerConfig | None = None,
        shutdown: GracefulShutdown | None = None,
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        self._targets = target_repository
        self._scheduler = scheduler
        self._owner_id = owner_id or generate_worker_owner_id()
        self._config = config or get_worker_config()
        self._shutdown = shutdown or GracefulShutdown()
        self._sleep_func = sleep_func

    @property
    def owner_id(self) -> str:
        return self._owner_id

    def run_once(
        self,
        *,
        ingest: bool = False,
        mall_id: str | None = None,
        target_id: str | None = None,
        ingest_client: IngestClient | None = None,
        max_targets: int | None = None,
        lease_seconds: int | None = None,
        now: datetime | None = None,
    ) -> WorkerRunResult:
        if not self._config.enabled:
            logger.info("worker disabled by configuration")
            empty = SchedulerRunResult(targets=[], results=[], summary=CrawlerBatchSummary())
            mark_cycle_started(worker_enabled=False)
            mark_cycle_finished(empty.summary)
            return WorkerRunResult(claimed_targets=[], skipped_targets=0, run=empty)

        run_at = now or utc_now()
        limit = max_targets if max_targets is not None else self._config.max_targets_per_cycle
        lease = lease_seconds if lease_seconds is not None else self._config.lease_seconds

        mark_cycle_started(worker_enabled=True)
        logger.info("cycle started", extra={"owner_id": self._owner_id})
        due_targets = self._scheduler.get_due_targets(
            run_at,
            mall_id=mall_id,
            target_id=target_id,
        )
        due_targets = due_targets[: max(int(limit), 0)]
        for target in due_targets:
            log_observability_event(
                logger,
                "target_due",
                target_id=target.target_id,
                mall_id=target.mall_id,
                product_url=target.product_url,
            )

        claimed_targets: list[CrawlTarget] = []
        skipped = 0
        for target in due_targets:
            if self._shutdown.should_stop:
                break
            claimed = self._targets.try_claim(
                target.target_id,
                self._owner_id,
                run_at,
                lease,
            )
            if claimed is None:
                skipped += 1
                record_lease_skip()
                logger.info(
                    "target skipped",
                    extra={"target_id": target.target_id, "reason": "not claimable"},
                )
                continue
            claimed_targets.append(claimed)
            record_lease_claim()
            log_observability_event(
                logger,
                "target_claimed",
                target_id=claimed.target_id,
                mall_id=claimed.mall_id,
            )
            logger.info(
                "lease acquired",
                extra={"target_id": claimed.target_id, "owner_id": self._owner_id},
            )

        results: list[CrawlerResult] = []
        summary = CrawlerBatchSummary()
        if claimed_targets and not self._shutdown.should_stop:
            try:
                results, summary = self._scheduler.run_target_batch(
                    claimed_targets,
                    ingest=ingest,
                    ingest_client=ingest_client,
                    now=run_at,
                )
            except Exception as exc:
                logger.error("cycle failed", extra={"error": str(exc)})
                for target in claimed_targets:
                    self._targets.release_lease(target.target_id, self._owner_id, now=utc_now())
                mark_cycle_finished(summary, error=str(exc))
                raise
        else:
            for target in claimed_targets:
                self._targets.release_lease(target.target_id, self._owner_id, now=utc_now())

        for target in claimed_targets:
            current = self._targets.get(target.target_id)
            if current is not None and current.lease_owner == self._owner_id:
                self._targets.release_lease(target.target_id, self._owner_id, now=utc_now())
                log_observability_event(
                    logger,
                    "lease_released",
                    target_id=target.target_id,
                    mall_id=target.mall_id,
                )
                logger.info("lease released", extra={"target_id": target.target_id})

        run = SchedulerRunResult(
            targets=claimed_targets,
            results=results,
            summary=summary,
        )
        logger.info(
            "cycle completed",
            extra={
                "claimed": len(claimed_targets),
                "skipped": skipped,
                "total": summary.total,
                "success": summary.success,
            },
        )
        mark_cycle_finished(summary)
        return WorkerRunResult(
            claimed_targets=claimed_targets,
            skipped_targets=skipped,
            run=run,
            shutdown_requested=self._shutdown.should_stop,
        )

    def run_forever(
        self,
        *,
        ingest: bool = False,
        mall_id: str | None = None,
        target_id: str | None = None,
        ingest_client: IngestClient | None = None,
        poll_interval_seconds: float | None = None,
        max_targets: int | None = None,
        lease_seconds: int | None = None,
        now: datetime | None = None,
    ) -> WorkerRunResult:
        interval = (
            poll_interval_seconds
            if poll_interval_seconds is not None
            else self._config.poll_interval_seconds
        )
        self._shutdown.register()
        logger.info("worker started", extra={"owner_id": self._owner_id})
        last_result = WorkerRunResult(
            claimed_targets=[],
            skipped_targets=0,
            run=SchedulerRunResult(targets=[], results=[], summary=CrawlerBatchSummary()),
        )
        try:
            while not self._shutdown.should_stop:
                last_result = self.run_once(
                    ingest=ingest,
                    mall_id=mall_id,
                    target_id=target_id,
                    ingest_client=ingest_client,
                    max_targets=max_targets,
                    lease_seconds=lease_seconds,
                    now=now,
                )
                if self._shutdown.should_stop:
                    break
                if interval > 0:
                    self._sleep_func(interval)
        finally:
            logger.info("worker stopped", extra={"owner_id": self._owner_id})
            self._shutdown.restore()
        return last_result
