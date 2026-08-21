"""Batch SSG product crawl CLI — dry-run by default, optional ingest."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.crawler.adapters.ssg import SSGCrawler
from pricebrain_app.crawler.client import IngestClient
from pricebrain_app.crawler.config import clear_crawler_config_cache
from pricebrain_app.crawler.results import CrawlerResult, CrawlerStatus


def _load_urls(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _format_dry_run_line(result: CrawlerResult) -> str:
    if result.payload is not None:
        payload = result.payload
        return (
            f"{result.status.value}\t"
            f"{result.product_url}\t"
            f"{payload.product_id}\t"
            f"{payload.product_name}\t"
            f"{payload.price}\t"
            f"{payload.mall_id}\t"
            f"{payload.crawled_at.isoformat()}"
        )
    return (
        f"{result.status.value}\t"
        f"{result.product_url or ''}\t"
        f"\t\t\t\t"
        f"{result.message}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sequentially crawl SSG product URLs from a file (dry-run default).",
    )
    parser.add_argument("--file", required=True, help="Text file with one URL per line")
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="POST successful payloads to /internal/ingest/listing",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=None,
        help="Override PRICEBRAIN_CRAWLER_MAX_RETRIES",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=None,
        help="Override PRICEBRAIN_CRAWLER_REQUEST_INTERVAL_SECONDS",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Override PRICEBRAIN_CRAWLER_TIMEOUT_SECONDS",
    )
    args = parser.parse_args(argv)

    url_file = Path(args.file)
    if not url_file.is_file():
        print(f"URL file not found: {url_file}", file=sys.stderr)
        return 1

    if args.max_retries is not None:
        os.environ["PRICEBRAIN_CRAWLER_MAX_RETRIES"] = str(args.max_retries)
    if args.interval is not None:
        os.environ["PRICEBRAIN_CRAWLER_REQUEST_INTERVAL_SECONDS"] = str(args.interval)
    if args.timeout is not None:
        os.environ["PRICEBRAIN_CRAWLER_TIMEOUT_SECONDS"] = str(args.timeout)
    clear_settings_cache()
    clear_crawler_config_cache()

    urls = _load_urls(url_file)
    ingest_client: IngestClient | None = None
    results = []

    try:
        with SSGCrawler() as crawler:
            if args.ingest:
                ingest_client = IngestClient()
            results, summary = crawler.crawl_urls_with_summary(
                urls,
                ingest=args.ingest,
                ingest_client=ingest_client,
                request_interval_seconds=args.interval,
            )

        print("status\turl\texternal_product_id\tproduct_name\tprice\tmall_id\tcrawled_at")
        for result in results:
            print(_format_dry_run_line(result))
        print()
        print(summary.format_summary())
    finally:
        if ingest_client is not None:
            ingest_client.close()

    has_hard_failure = any(
        result.status
        not in {CrawlerStatus.SUCCESS, CrawlerStatus.SKIPPED, CrawlerStatus.HTTP_ERROR}
        for result in results
    )
    return 1 if has_hard_failure and summary.success == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
