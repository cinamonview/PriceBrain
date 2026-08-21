"""Show price alert runner health."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.alert_operations_cli import build_alert_operations_view
from pricebrain_app.crawler.alert_operations_format import format_runner_health
from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction, print_error, print_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show price alert runner health.")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--recent", type=int, default=5, help="Recent cycle count")
    args = parser.parse_args(argv)

    try:
        view = build_alert_operations_view()
        health = view.get_runner_health(recent_limit=args.recent)
    except Exception as exc:
        print_error(f"Error: {exc}")
        return 1

    if args.json:
        print_json(health.to_dict(), secrets=collect_secrets_for_redaction())
        return 0

    print(format_runner_health(health))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
