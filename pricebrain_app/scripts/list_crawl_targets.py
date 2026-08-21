"""List crawl targets with operational filters."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.ops_cli import (
    build_operations_view,
    collect_secrets_for_redaction,
    print_error,
    print_json,
)
from pricebrain_app.crawler.ops_format import format_target_list
from pricebrain_app.crawler.operations_view import TargetListFilter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List crawl targets.")
    parser.add_argument("--mall", help="Filter by mall_id")
    parser.add_argument("--enabled", action="store_true", help="Show enabled targets only")
    parser.add_argument("--disabled", action="store_true", help="Show disabled targets only")
    parser.add_argument("--due", action="store_true", help="Show due targets only")
    parser.add_argument("--failed", action="store_true", help="Show failed targets only")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    enabled = None
    if args.enabled and args.disabled:
        print_error("Error: use either --enabled or --disabled, not both")
        return 1
    if args.enabled:
        enabled = True
    if args.disabled:
        enabled = False

    secrets = collect_secrets_for_redaction()
    try:
        view = build_operations_view()
        targets = view.list_targets(
            filters=TargetListFilter(
                mall_id=args.mall,
                enabled=enabled,
                due_only=args.due,
                failed_only=args.failed,
            )
        )
    except Exception as exc:
        print_error(f"Error: {exc}")
        return 1

    if args.json:
        print_json([target.to_dict() for target in targets], secrets=secrets)
        return 0

    print(format_target_list(targets))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
