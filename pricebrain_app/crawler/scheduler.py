"""Crawler scheduler abstraction — due target selection and one-shot runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

from pricebrain_app.crawler.adapters.elevenst import ElevenstCrawler
from pricebrain_app.crawler.adapters.ssg import SSGCrawler
from pricebrain_app.crawler.base import BaseCrawler
from pricebrain_app.crawler.client import IngestClient
from pricebrain_app.crawler.logging_utils import get_crawler_logger, safe_url_for_log
from pricebrain_app.crawler.metrics import record_crawl_result, record_ingest_success
from pricebrain_app.crawler.observability_events import crawl_event_for_status, log_observability_event
from pricebrain_app.crawler.operations import ingest_result
from pricebrain_app.crawler.results import CrawlerBatchSummary, CrawlerResult, CrawlerStatus
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.targets import CrawlTarget, utc_now

logger = get_crawler_logger()

_CRAWLER_FACTORIES: dict[str, Callable[[], BaseCrawler]] = {
    "ssg": SSGCrawler,
    "elevenst": ElevenstCrawler,
}


@dataclass(frozen=True)
class SchedulerRunResult:
    targets: list[CrawlTarget]
    results: list[CrawlerResult]
    summary: CrawlerBatchSummary


class CrawlerScheduler:
    """Select due crawl targets and run one batch without OS/cloud scheduler coupling."""

    def __init__(
        self,
        target_repository: CrawlTargetRepository,
        *,
        crawler_factory: Callable[[], SSGCrawler] | None = None,
    ) -> None:
        self._targets = target_repository
        self._crawler_factory = crawler_factory or SSGCrawler

    def calculate_next_run(
        self,
        now: datetime,
        interval_seconds: int,
        status: CrawlerStatus,
    ) -> datetime:
        _ = status
        return now + timedelta(seconds=max(int(interval_seconds), 1))

    def get_due_targets(
        self,
        now: datetime | None = None,
        *,
        mall_id: str | None = None,
        target_id: str | None = None,
    ) -> list[CrawlTarget]:
        run_at = now or utc_now()
        return self._targets.list_due(run_at, mall_id=mall_id, target_id=target_id)

    def run_target_batch(
        self,
        targets: list[CrawlTarget],
        *,
        ingest: bool = False,
        ingest_client: IngestClient | None = None,
        now: datetime | None = None,
        sleep_func: Callable[[float], None] | None = None,
    ) -> tuple[list[CrawlerResult], CrawlerBatchSummary]:
        _ = sleep_func
        run_at = now or utc_now()
        results: list[CrawlerResult] = []

        if not targets:
            return results, CrawlerBatchSummary()

        for target in targets:
            logger.info(
                "scheduler running target",
                extra={
                    "target_id": target.target_id,
                    "url": safe_url_for_log(target.product_url),
                },
            )
            log_observability_event(
                logger,
                "crawl_started",
                target_id=target.target_id,
                mall_id=target.mall_id,
                product_url=target.product_url,
            )
            result = self._crawl_target(target)
            record_crawl_result(result.status)
            log_observability_event(
                logger,
                crawl_event_for_status(result.status.value),
                target_id=target.target_id,
                mall_id=target.mall_id,
                status=result.status.value,
                error_code=result.message or None,
                elapsed_ms=result.elapsed_ms,
                price=result.payload.price if result.payload is not None else None,
                product_url=target.product_url,
            )
            if ingest and result.status == CrawlerStatus.SUCCESS:
                log_observability_event(
                    logger,
                    "ingest_started",
                    target_id=target.target_id,
                    mall_id=target.mall_id,
                )
                if ingest_client is None:
                    result = CrawlerResult(
                        status=CrawlerStatus.INGEST_ERROR,
                        mall_id=target.mall_id,
                        product_url=target.product_url,
                        external_product_id=result.external_product_id,
                        message="IngestClient is required when ingest=True",
                        retry_count=result.retry_count,
                        elapsed_ms=result.elapsed_ms,
                        crawled_at=result.crawled_at,
                        payload=result.payload,
                    )
                else:
                    result = ingest_result(result, ingest_client)
                    if result.status == CrawlerStatus.SUCCESS:
                        record_ingest_success()
                        log_observability_event(
                            logger,
                            "ingest_success",
                            target_id=target.target_id,
                            mall_id=target.mall_id,
                        )
                    else:
                        log_observability_event(
                            logger,
                            "ingest_error",
                            target_id=target.target_id,
                            mall_id=target.mall_id,
                            status=result.status.value,
                        )

            next_run = self.calculate_next_run(
                run_at,
                target.crawl_interval_seconds,
                result.status,
            )
            self._targets.update_after_crawl(
                target.target_id,
                result=result,
                next_crawl_at=next_run,
                crawled_at=parse_crawled_at(result, run_at),
            )
            log_observability_event(
                logger,
                "target_updated",
                target_id=target.target_id,
                mall_id=target.mall_id,
                status=result.status.value,
            )
            results.append(result)

        return results, CrawlerBatchSummary.from_results(results)

    def run_once(
        self,
        *,
        ingest: bool = False,
        mall_id: str | None = None,
        target_id: str | None = None,
        ingest_client: IngestClient | None = None,
        now: datetime | None = None,
    ) -> SchedulerRunResult:
        due_targets = self.get_due_targets(now, mall_id=mall_id, target_id=target_id)
        results, summary = self.run_target_batch(
            due_targets,
            ingest=ingest,
            ingest_client=ingest_client,
            now=now,
        )
        return SchedulerRunResult(targets=due_targets, results=results, summary=summary)

    def _crawl_target(self, target: CrawlTarget) -> CrawlerResult:
        mall = target.mall_id.strip().lower()
        if mall == "ssg":
            factory: Callable[[], BaseCrawler] = self._crawler_factory
        else:
            factory = _CRAWLER_FACTORIES.get(mall)
        if factory is None:
            return CrawlerResult(
                status=CrawlerStatus.VALIDATION_ERROR,
                mall_id=target.mall_id,
                product_url=target.product_url,
                message=f"Unsupported mall for scheduler crawl: {target.mall_id}",
            )
        with factory() as crawler:
            return crawler.crawl_product_url_result(target.product_url)


def parse_crawled_at(result: CrawlerResult, fallback: datetime) -> datetime:
    if not result.crawled_at:
        return fallback
    from pricebrain_app.crawler.targets import parse_datetime

    parsed = parse_datetime(result.crawled_at)
    return parsed or fallback
