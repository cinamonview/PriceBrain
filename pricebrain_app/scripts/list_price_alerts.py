"""List configured price alerts."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction, print_json
from pricebrain_app.crawler.price_alert_cli import build_price_alert_repository


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List price alerts.")
    parser.add_argument("--target-id", help="Filter by crawl target ID")
    parser.add_argument("--enabled-only", action="store_true", help="Show enabled alerts only")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    try:
        repo = build_price_alert_repository()
        enabled = True if args.enabled_only else None
        alerts = repo.list_all(
            target_id=args.target_id.strip() if args.target_id else None,
            enabled=enabled,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    payload = [alert.to_firestore_dict() for alert in alerts]
    if args.json:
        print_json(payload, secrets=collect_secrets_for_redaction())
        return 0

    print(format_alert_list(alerts))
    return 0


def format_alert_list(alerts) -> str:
    if not alerts:
        return "No price alerts found."
    lines = ["Price Alerts", ""]
    for alert in alerts:
        lines.extend(
            [
                f"{alert.alert_id} [{alert.alert_type.value}]",
                f"  target: {alert.target_id}",
                f"  threshold: {alert.threshold}",
                f"  enabled: {str(alert.enabled).lower()}",
                f"  last_triggered_at: {alert.last_triggered_at or '-'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


if __name__ == "__main__":
    raise SystemExit(main())
