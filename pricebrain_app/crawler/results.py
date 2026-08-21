"""Crawler operational result models — batch-safe success/failure reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pricebrain_app.crawler.models import IngestListingPayload


class CrawlerStatus(StrEnum):
    SUCCESS = "SUCCESS"
    HTTP_ERROR = "HTTP_ERROR"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    PARSE_ERROR = "PARSE_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INGEST_ERROR = "INGEST_ERROR"
    SKIPPED = "SKIPPED"


@dataclass
class CrawlerResult:
    status: CrawlerStatus
    mall_id: str
    product_url: str | None = None
    external_product_id: str | None = None
    message: str = ""
    retry_count: int = 0
    elapsed_ms: int = 0
    crawled_at: str | None = None
    http_status_code: int | None = None
    payload: IngestListingPayload | None = None
    ingest_response: dict[str, Any] | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "status": self.status.value,
            "mall_id": self.mall_id,
            "product_url": self.product_url,
            "external_product_id": self.external_product_id,
            "message": self.message,
            "retry_count": self.retry_count,
            "elapsed_ms": self.elapsed_ms,
            "crawled_at": self.crawled_at,
            "http_status_code": self.http_status_code,
        }
        if self.payload is not None:
            data["payload"] = self.payload.to_dict()
        if self.ingest_response is not None:
            data["ingest_response"] = self.ingest_response
        return data


@dataclass(frozen=True)
class CrawlerBatchSummary:
    total: int = 0
    success: int = 0
    http_error: int = 0
    timeout: int = 0
    network_error: int = 0
    parse_error: int = 0
    validation_error: int = 0
    ingest_error: int = 0
    skipped: int = 0

    @classmethod
    def from_results(cls, results: list[CrawlerResult]) -> CrawlerBatchSummary:
        counts = {status: 0 for status in CrawlerStatus}
        for result in results:
            counts[result.status] += 1
        return cls(
            total=len(results),
            success=counts[CrawlerStatus.SUCCESS],
            http_error=counts[CrawlerStatus.HTTP_ERROR],
            timeout=counts[CrawlerStatus.TIMEOUT],
            network_error=counts[CrawlerStatus.NETWORK_ERROR],
            parse_error=counts[CrawlerStatus.PARSE_ERROR],
            validation_error=counts[CrawlerStatus.VALIDATION_ERROR],
            ingest_error=counts[CrawlerStatus.INGEST_ERROR],
            skipped=counts[CrawlerStatus.SKIPPED],
        )

    def format_summary(self) -> str:
        lines = [
            "Crawler summary",
            "",
            f"total: {self.total}",
            f"success: {self.success}",
            f"http_error: {self.http_error}",
            f"timeout: {self.timeout}",
            f"network_error: {self.network_error}",
            f"parse_error: {self.parse_error}",
            f"validation_error: {self.validation_error}",
            f"ingest_error: {self.ingest_error}",
            f"skipped: {self.skipped}",
        ]
        return "\n".join(lines)
