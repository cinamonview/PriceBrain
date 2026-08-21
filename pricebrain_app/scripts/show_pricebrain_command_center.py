"""Show the PriceBrain read-only operations command center."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.command_center_operations_cli import build_command_center_operations_view
from pricebrain_app.crawler.command_center_operations_format import format_command_center
from pricebrain_app.crawler.command_center_operations_models import CommandCenterFilter
from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction, print_error, print_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show the PriceBrain operations command center.")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--recent", type=int, default=10, help="Recent execution history count")
    parser.add_argument("--failures", action="store_true", help="Show execution failures only")
    parser.add_argument("--blocked", action="store_true", help="Show blocked executions only")
    parser.add_argument("--action-id", help="Filter execution history by action_id")
    parser.add_argument("--target-id", help="Filter execution history by target_id")
    parser.add_argument("--alert-id", help="Filter execution history by alert_id")
    parser.add_argument("--mall", help="Filter dashboard by mall_id")
    parser.add_argument("--category", default="gpu", help="Filter dashboard by category")
    parser.add_argument("--tag", help="Filter dashboard by tag")
    args = parser.parse_args(argv)

    filters = CommandCenterFilter(
        mall_id=args.mall,
        category=args.category,
        tag=args.tag,
        recent=max(int(args.recent), 1),
        failures_only=args.failures,
        blocked_only=args.blocked,
        action_id=args.action_id,
        target_id=args.target_id,
        alert_id=args.alert_id,
    )

    try:
        view = build_command_center_operations_view()
        snapshot = view.build_snapshot(filters=filters)
    except Exception as exc:
        print_error(f"Error: {exc}")
        return 1

    if args.json:
        print_json(snapshot.to_dict(), secrets=collect_secrets_for_redaction())
        return 0

    print(format_command_center(snapshot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
