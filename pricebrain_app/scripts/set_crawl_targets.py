"""Bulk enable or disable crawl targets by operational filters."""

from __future__ import annotations

import argparse
import json
import sys

from pricebrain_app.crawler.target_management import BulkUpdateFilter, bulk_set_enabled
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.firebase.admin import get_firestore_client


def _parse_enabled(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError("enabled must be true or false")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bulk enable or disable crawl targets.")
    parser.add_argument("--mall", help="Filter by mall_id")
    parser.add_argument("--category", help="Filter by category")
    parser.add_argument("--tag", help="Filter by tag")
    parser.add_argument(
        "--enabled",
        type=_parse_enabled,
        required=True,
        help="Set enabled state (true/false)",
    )
    args = parser.parse_args(argv)

    if not any([args.mall, args.category, args.tag]):
        print(
            "Error: specify at least one filter (--mall, --category, or --tag)",
            file=sys.stderr,
        )
        return 1

    try:
        db = get_firestore_client()
        repo = CrawlTargetRepository(db)
        updated = bulk_set_enabled(
            repo,
            enabled=args.enabled,
            filters=BulkUpdateFilter(
                mall_id=args.mall,
                category=args.category,
                tag=args.tag,
            ),
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "updated": updated,
                "enabled": args.enabled,
                "filters": {
                    "mall_id": args.mall,
                    "category": args.category,
                    "tag": args.tag,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
