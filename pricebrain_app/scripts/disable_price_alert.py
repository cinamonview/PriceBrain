"""Disable a price alert."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction, print_json
from pricebrain_app.crawler.price_alert_cli import build_price_alert_repository


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Disable a price alert.")
    parser.add_argument("--alert-id", required=True, help="Price alert ID")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    try:
        repo = build_price_alert_repository()
        alert_id = args.alert_id.strip()
        current = repo.get(alert_id)
        if current is None:
            print(f"Error: alert not found: {alert_id}", file=sys.stderr)
            return 1
        alert = repo.set_enabled(alert_id, enabled=False)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print_json(alert.to_firestore_dict(), secrets=collect_secrets_for_redaction())
    else:
        print(f"Disabled price alert: {alert.alert_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
