"""Backfill price history from a Danawa-Crawler VGA.csv (read from disk, no network)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from pricebrain_app.danawa_import import (
    DanawaImportSetupError,
    ImportReport,
    import_danawa_products,
    parse_danawa_csv,
)
from pricebrain_app.firebase.admin import get_firestore_client


def _print_report(report: ImportReport, *, dry_run: bool) -> None:
    mode = "DRY-RUN (nothing written)" if dry_run else "IMPORT"
    print(f"{mode}")
    print(f"rows read:             {report.rows}")
    print(f"accepted by gates:     {report.accepted}")
    if not dry_run:
        print(f"listings written:      {report.listings_written}")
        print(f"price points written:  {report.price_points_written}")
    if report.skipped:
        print("skipped:")
        for category, count in report.skipped.most_common():
            sample = "; ".join(report.examples[category])
            print(f"  {count:5d}  {category}   e.g. {sample}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import Danawa-Crawler VGA.csv price history through the PriceBrain pipeline.",
    )
    parser.add_argument("--csv", required=True, type=Path, help="Path to Danawa-Crawler VGA.csv")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run every gate but write nothing; prints what would be accepted or skipped.",
    )
    parser.add_argument("--limit", type=int, help="Only read the first N CSV rows.")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="Write without FIRESTORE_EMULATOR_HOST (real Firestore). Off by default.",
    )
    args = parser.parse_args(argv)

    if not args.dry_run and not os.environ.get("FIRESTORE_EMULATOR_HOST") and not args.allow_production:
        print(
            "Refusing to write: FIRESTORE_EMULATOR_HOST is not set. "
            "Start the emulator and set it, or pass --allow-production.",
            file=sys.stderr,
        )
        return 2

    try:
        products = parse_danawa_csv(args.csv)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if args.limit is not None:
        products = products[: args.limit]

    def progress(done: int, total: int) -> None:
        if not args.json and (done % 50 == 0 or done == total):
            print(f"  ... {done}/{total} products", file=sys.stderr)

    try:
        report = import_danawa_products(
            get_firestore_client(),
            products,
            dry_run=args.dry_run,
            progress=progress,
        )
    except DanawaImportSetupError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        _print_report(report, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
