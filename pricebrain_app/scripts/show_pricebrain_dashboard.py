"""Show the PriceBrain read-only operations dashboard."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.dashboard_operations_cli import build_dashboard_operations_view
from pricebrain_app.crawler.dashboard_operations_format import format_dashboard
from pricebrain_app.crawler.dashboard_operations_models import DashboardFilter
from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction, print_error, print_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show the PriceBrain operations dashboard.")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--recent", type=int, default=10, help="Recent event count")
    parser.add_argument("--failures", action="store_true", help="Focus on failure-oriented audit data")
    parser.add_argument("--mall", help="Filter by mall_id")
    parser.add_argument("--category", default="gpu", help="Filter by category (default: gpu)")
    parser.add_argument("--tag", help="Filter by tag")
    args = parser.parse_args(argv)

    filters = DashboardFilter(
        mall_id=args.mall,
        category=args.category,
        tag=args.tag,
        recent=max(int(args.recent), 1),
        failures_only=args.failures,
    )

    try:
        view = build_dashboard_operations_view()
        snapshot = view.build_dashboard_snapshot(filters=filters)
    except Exception as exc:
        print_error(f"Error: {exc}")
        return 1

    if args.json:
        print_json(snapshot.to_dict(), secrets=collect_secrets_for_redaction())
        return 0

    print(format_dashboard(snapshot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
