"""Run crawler scheduler once — dry-run by default (no ingest)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from pricebrain_app.crawler.client import IngestClient
from pricebrain_app.crawler.scheduler import CrawlerScheduler
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.firebase.admin import get_firestore_client


def _format_target_preview(target) -> dict:
    return {
        "target_id": target.target_id,
        "mall_id": target.mall_id,
        "product_url": target.product_url,
        "enabled": target.enabled,
        "crawl_interval_seconds": target.crawl_interval_seconds,
        "next_crawl_at": target.next_crawl_at.isoformat() if target.next_crawl_at else None,
        "last_status": target.last_status,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run PriceBrain crawler scheduler (preview by default).",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Execute one scheduler run for due targets",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="POST successful crawls to /internal/ingest/listing",
    )
    parser.add_argument("--mall", help="Filter by mall_id (e.g. ssg)")
    parser.add_argument("--target-id", help="Run a specific crawl target only")
    args = parser.parse_args(argv)

    try:
        db = get_firestore_client()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    repo = CrawlTargetRepository(db)
    scheduler = CrawlerScheduler(repo)
    now = datetime.now(timezone.utc)

    if not args.once:
        due = scheduler.get_due_targets(now, mall_id=args.mall, target_id=args.target_id)
        print(json.dumps([_format_target_preview(item) for item in due], ensure_ascii=False, indent=2))
        print(f"\nDue targets: {len(due)} (dry-run preview; use --once to execute)")
        return 0

    ingest_client: IngestClient | None = None
    try:
        if args.ingest:
            ingest_client = IngestClient()
        run = scheduler.run_once(
            ingest=args.ingest,
            mall_id=args.mall,
            target_id=args.target_id,
            ingest_client=ingest_client,
            now=now,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        if ingest_client is not None:
            ingest_client.close()

    for result in run.results:
        line = {
            "target_id": next(
                (target.target_id for target in run.targets if target.product_url == result.product_url),
                None,
            ),
            "status": result.status.value,
            "product_url": result.product_url,
            "external_product_id": result.external_product_id,
            "message": result.message,
            "crawled_at": result.crawled_at,
        }
        if result.payload is not None:
            line["price"] = result.payload.price
        print(json.dumps(line, ensure_ascii=False))

    print()
    print(run.summary.format_summary())
    return 0 if run.summary.success > 0 or run.summary.total == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
