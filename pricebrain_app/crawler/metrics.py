"""In-memory crawler metrics — extensible to external observability backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

from pricebrain_app.crawler.results import CrawlerStatus


@dataclass
class CrawlerMetrics:
    crawl_attempts: int = 0
    crawl_successes: int = 0
    crawl_http_errors: int = 0
    crawl_parse_errors: int = 0
    crawl_timeouts: int = 0
    crawl_network_errors: int = 0
    ingest_successes: int = 0
    ingest_errors: int = 0
    lease_claims: int = 0
    lease_skips: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "crawl_attempts": self.crawl_attempts,
            "crawl_successes": self.crawl_successes,
            "crawl_http_errors": self.crawl_http_errors,
            "crawl_parse_errors": self.crawl_parse_errors,
            "crawl_timeouts": self.crawl_timeouts,
            "crawl_network_errors": self.crawl_network_errors,
            "ingest_successes": self.ingest_successes,
            "ingest_errors": self.ingest_errors,
            "lease_claims": self.lease_claims,
            "lease_skips": self.lease_skips,
        }


_lock = Lock()
_metrics = CrawlerMetrics()


def get_crawler_metrics() -> CrawlerMetrics:
    with _lock:
        return CrawlerMetrics(**_metrics.to_dict())


def reset_crawler_metrics() -> None:
    global _metrics
    with _lock:
        _metrics = CrawlerMetrics()


def record_crawl_result(status: CrawlerStatus) -> None:
    with _lock:
        _metrics.crawl_attempts += 1
        if status == CrawlerStatus.SUCCESS:
            _metrics.crawl_successes += 1
        elif status == CrawlerStatus.HTTP_ERROR:
            _metrics.crawl_http_errors += 1
        elif status == CrawlerStatus.PARSE_ERROR:
            _metrics.crawl_parse_errors += 1
        elif status == CrawlerStatus.TIMEOUT:
            _metrics.crawl_timeouts += 1
        elif status == CrawlerStatus.NETWORK_ERROR:
            _metrics.crawl_network_errors += 1
        elif status == CrawlerStatus.INGEST_ERROR:
            _metrics.ingest_errors += 1


def record_ingest_success() -> None:
    with _lock:
        _metrics.ingest_successes += 1


def record_lease_claim() -> None:
    with _lock:
        _metrics.lease_claims += 1


def record_lease_skip() -> None:
    with _lock:
        _metrics.lease_skips += 1
