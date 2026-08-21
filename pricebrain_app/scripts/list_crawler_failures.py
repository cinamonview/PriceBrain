"""List recent crawler failures."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.ops_cli import (
    build_operations_view,
    collect_secrets_for_redaction,
    print_error,
    print_json,
)
from pricebrain_app.crawler.ops_format import format_failure_list


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List recent crawler target failures.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum failures to show")
    parser.add_argument("--mall", help="Filter by mall_id")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)
    secrets = collect_secrets_for_redaction()

    try:
        view = build_operations_view()
        failures = view.list_recent_failures(limit=args.limit, mall_id=args.mall)
    except Exception as exc:
        print_error(f"Error: {exc}")
        return 1

    if args.json:
        print_json([item.to_dict() for item in failures], secrets=secrets)
        return 0

    print(format_failure_list(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
