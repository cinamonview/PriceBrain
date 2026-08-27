"""Bounded 11번가 search batch — V2 Phase 3.

Dry-run is the default. Persisting requires --persist *and* either the Firestore
emulator or an explicit --confirm-production, mirroring scripts/seed_gpu_master.py.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from collections import Counter

from pricebrain_app.crawler.adapters.elevenst import ElevenstCrawler, ElevenstHtmlFetcher
from pricebrain_app.crawler.config import build_http_client
from pricebrain_app.crawler.parser.elevenst_search import parse_elevenst_search_json
from pricebrain_app.search_batch import (
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_SEARCH_PAGES,
    MAX_SEARCH_LIMIT,
    MAX_SEARCH_PAGES,
    SearchItemStatus,
    run_search_batch,
)
from pricebrain_app.firebase.admin import get_firestore_client


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a bounded 11번가 search batch")
    parser.add_argument("--query", required=True, help="Search keyword (required)")
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_SEARCH_LIMIT,
        help=f"Max results to process (default {DEFAULT_SEARCH_LIMIT}, hard cap {MAX_SEARCH_LIMIT})",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=DEFAULT_SEARCH_PAGES,
        help=f"Search pages to walk (default {DEFAULT_SEARCH_PAGES}, hard cap {MAX_SEARCH_PAGES})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=25.0,
        help="Per-request HTTP timeout in seconds (default 25)",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Write to Firestore. Without this flag the batch is a dry-run.",
    )
    parser.add_argument(
        "--confirm-production",
        action="store_true",
        help="Allow --persist against real Firestore (no emulator)",
    )
    parser.add_argument(
        "--fixture",
        type=pathlib.Path,
        default=None,
        help="Classify a saved search JSON file instead of making HTTP requests",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the summary as JSON",
    )
    return parser


def _guard_persist(args: argparse.Namespace) -> None:
    """Refuse silent production writes — §9 keeps production read-only by default."""
    if not args.persist:
        return
    if os.environ.get("FIRESTORE_EMULATOR_HOST"):
        return
    if args.confirm_production:
        return
    print(
        "Refusing to persist: set FIRESTORE_EMULATOR_HOST or pass --confirm-production",
        file=sys.stderr,
    )
    raise SystemExit(1)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    _guard_persist(args)

    dry_run = not args.persist
    crawler: ElevenstCrawler | None = None

    if args.fixture is not None:
        payload = json.loads(args.fixture.read_text(encoding="utf-8"))
        items = parse_elevenst_search_json(payload)

        def search_page(_query: str, page: int):
            return items if page == 1 else []
    else:
        crawler = ElevenstCrawler(
            fetcher=ElevenstHtmlFetcher(build_http_client(timeout=args.timeout))
        )

        def search_page(query: str, page: int):
            return crawler.search(query, page=page)

    try:
        db = get_firestore_client()
        results, summary = run_search_batch(
            query=args.query,
            search_page=search_page,
            db=db,
            limit=args.limit,
            pages=args.pages,
            dry_run=dry_run,
        )
    finally:
        if crawler is not None:
            crawler.close()

    if args.json:
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
        return 0

    print(summary.format_summary())

    error_categories = Counter(
        item.error_category
        for item in results
        if item.status
        in (SearchItemStatus.VALIDATION_FAILED, SearchItemStatus.FAILED)
        and item.error_category
    )
    if error_categories:
        print("\nerror categories:")
        for category, count in error_categories.most_common():
            print(f"  {category:24} {count}")

    print("\nper-result:")
    for item in results:
        print(
            f"  p{item.page} #{item.rank:<3} {item.status.value:18} "
            f"{(item.gpu_model_id or '-'):16} {item.product_name[:56]}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
