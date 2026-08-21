"""Seed GPU crawl targets from a JSON catalog file."""

from __future__ import annotations

import argparse
import json
import sys

from pricebrain_app.crawler.target_management import SeedResult, seed_gpu_catalog_file
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and preview changes without writing to Firestore",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON summary")
    args = parser.parse_args(argv)

    try:
        db = get_firestore_client()
        repo = CrawlTargetRepository(db)
        result = seed_gpu_catalog_file(repo, args.file, dry_run=args.dry_run)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_seed_result(result, dry_run=args.dry_run))

    return 1 if result.invalid else 0


def format_seed_result(result: SeedResult, *, dry_run: bool) -> str:
    prefix = "Dry-run " if dry_run else ""
    lines = [
        f"{prefix}Seed Summary",
        f"total: {result.total}",
        f"created: {result.created}",
        f"updated: {result.updated}",
        f"skipped: {result.skipped}",
        f"invalid: {result.invalid}",
    ]
    if result.errors:
        lines.extend(["", "errors:"])
        lines.extend(f"  - {error}" for error in result.errors)
    if dry_run and result.previews:
        lines.extend(["", "planned changes:"])
        for preview in result.previews:
            if preview.action == "skip":
                lines.append(f"  {preview.target_id}: skip")
                continue
            lines.append(f"  {preview.target_id}: {preview.action}")
            for field, current, planned in preview.changes:
                lines.append(f"    {field}: {current!r} -> {planned!r}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
