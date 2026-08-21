"""Register or update a crawl target in Firestore."""

from __future__ import annotations

import argparse
import json
import sys

from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.targets import DEFAULT_CRAWL_INTERVAL_SECONDS
from pricebrain_app.firebase.admin import get_firestore_client


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Register a crawl target in Firestore.")
    parser.add_argument("--mall", required=True, help="Mall ID (e.g. ssg)")
    parser.add_argument("--url", required=True, help="Product detail URL")
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_CRAWL_INTERVAL_SECONDS,
        help="Crawl interval in seconds (default: 3600)",
    )
    parser.add_argument(
        "--disabled",
        action="store_true",
        help="Register target as disabled",
    )
    args = parser.parse_args(argv)

    try:
        db = get_firestore_client()
        repo = CrawlTargetRepository(db)
        target = repo.upsert(
            mall_id=args.mall,
            product_url=args.url,
            enabled=not args.disabled,
            crawl_interval_seconds=args.interval,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    output = {
        "target_id": target.target_id,
        "mall_id": target.mall_id,
        "product_url": target.product_url,
        "enabled": target.enabled,
        "crawl_interval_seconds": target.crawl_interval_seconds,
        "next_crawl_at": target.next_crawl_at.isoformat() if target.next_crawl_at else None,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
