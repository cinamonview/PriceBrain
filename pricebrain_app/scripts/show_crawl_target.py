"""Show a single crawl target in detail."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.ops_cli import (
    build_operations_view,
    collect_secrets_for_redaction,
    print_error,
    print_json,
)
from pricebrain_app.crawler.ops_format import format_target_detail


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show crawl target details.")
    parser.add_argument("--target-id", required=True, help="crawler_targets document ID")
    parser.add_argument(
        "--with-price-history",
        action="store_true",
        help="Include read-only price history summary when listing exists",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)
    secrets = collect_secrets_for_redaction()

    try:
        view = build_operations_view()
        target = view.get_target(args.target_id.strip())
        if target is None:
            print_error(f"Target not found: crawler_targets/{args.target_id}")
            return 1
        price_view = None
        if args.with_price_history:
            price_view = view.get_price_change_for_target(target.target_id)
    except Exception as exc:
        print_error(f"Error: {exc}")
        return 1

    if args.json:
        payload = target.to_dict()
        if price_view is not None:
            payload["price_history"] = price_view.to_dict()
        print_json(payload, secrets=secrets)
        return 0

    print(format_target_detail(target, price_view=price_view))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
