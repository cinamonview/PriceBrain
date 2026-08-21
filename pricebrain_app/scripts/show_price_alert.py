"""Show a single price alert operations snapshot."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.alert_operations_cli import build_alert_operations_view
from pricebrain_app.crawler.alert_operations_format import format_alert_snapshot
from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction, print_error, print_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show a price alert operations snapshot.")
    parser.add_argument("--alert-id", required=True, help="Price alert ID")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    try:
        view = build_alert_operations_view()
        snapshot = view.get_alert_snapshot(args.alert_id.strip())
    except Exception as exc:
        print_error(f"Error: {exc}")
        return 1

    if snapshot is None:
        print_error(f"Alert not found: {args.alert_id}")
        return 1

    if args.json:
        print_json(snapshot.to_dict(), secrets=collect_secrets_for_redaction())
        return 0

    print(format_alert_snapshot(snapshot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
