"""Seed GPU crawl targets from a JSON catalog file."""

from __future__ import annotations

import argparse
import json
import sys

from pricebrain_app.crawler.target_management import load_catalog_entries_from_file, seed_catalog_entries
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.firebase.admin import get_firestore_client


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Register or merge GPU crawl targets from a JSON catalog file."
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Path to JSON catalog file (array of target entries)",
    )
    args = parser.parse_args(argv)

    try:
        entries = load_catalog_entries_from_file(args.file)
        db = get_firestore_client()
        repo = CrawlTargetRepository(db)
        result = seed_catalog_entries(repo, entries)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    output = {
        "created": result.created,
        "updated": result.updated,
        "errors": result.errors,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
