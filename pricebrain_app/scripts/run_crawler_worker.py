"""Continuous crawler worker CLI — claim, crawl, optional ingest."""

from __future__ import annotations

import argparse
import json
import os
import sys

from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.crawler.client import IngestClient
from pricebrain_app.crawler.config import clear_crawler_config_cache
from pricebrain_app.crawler.scheduler import CrawlerScheduler
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.worker import CrawlerWorker
from pricebrain_app.firebase.admin import get_firestore_client


def build_worker_from_env(
    *,
    poll_interval: float | None = None,
    max_targets: int | None = None,
    lease_seconds: int | None = None,
) -> CrawlerWorker:
    if poll_interval is not None:
        os.environ["PRICEBRAIN_CRAWLER_POLL_INTERVAL_SECONDS"] = str(poll_interval)
    if max_targets is not None:
        os.environ["PRICEBRAIN_CRAWLER_MAX_TARGETS_PER_CYCLE"] = str(max_targets)
    if lease_seconds is not None:
        os.environ["PRICEBRAIN_CRAWLER_LEASE_SECONDS"] = str(lease_seconds)
    clear_settings_cache()
    clear_crawler_config_cache()

    db = get_firestore_client()
    repo = CrawlTargetRepository(db)
    scheduler = CrawlerScheduler(repo)
    return CrawlerWorker(repo, scheduler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run PriceBrain crawler worker.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one worker cycle and exit",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="POST successful crawls to /internal/ingest/listing",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=None,
        help="Override PRICEBRAIN_CRAWLER_POLL_INTERVAL_SECONDS",
    )
    parser.add_argument("--mall", help="Filter by mall_id (e.g. ssg)")
    parser.add_argument("--target-id", help="Run a specific crawl target only")
    parser.add_argument(
        "--max-targets",
        type=int,
        default=None,
        help="Override PRICEBRAIN_CRAWLER_MAX_TARGETS_PER_CYCLE",
    )
    parser.add_argument(
        "--lease-seconds",
        type=int,
        default=None,
        help="Override PRICEBRAIN_CRAWLER_LEASE_SECONDS",
    )
    args = parser.parse_args(argv)

    try:
        worker = build_worker_from_env(
            poll_interval=args.poll_interval,
            max_targets=args.max_targets,
            lease_seconds=args.lease_seconds,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    ingest_client: IngestClient | None = None
    try:
        if args.ingest:
            ingest_client = IngestClient()
        if args.once:
            result = worker.run_once(
                ingest=args.ingest,
                mall_id=args.mall,
                target_id=args.target_id,
                ingest_client=ingest_client,
                max_targets=args.max_targets,
                lease_seconds=args.lease_seconds,
            )
        else:
            result = worker.run_forever(
                ingest=args.ingest,
                mall_id=args.mall,
                target_id=args.target_id,
                ingest_client=ingest_client,
                poll_interval_seconds=args.poll_interval,
                max_targets=args.max_targets,
                lease_seconds=args.lease_seconds,
            )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        if ingest_client is not None:
            ingest_client.close()

    for crawl_result in result.results:
        print(json.dumps(crawl_result.to_dict(), ensure_ascii=False))

    print()
    print(result.summary.format_summary())
    print(f"claimed={len(result.claimed_targets)} skipped={result.skipped_targets}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
