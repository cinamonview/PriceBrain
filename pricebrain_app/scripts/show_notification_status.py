"""Show notification operations status."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.alert_operations_cli import build_alert_operations_view
from pricebrain_app.crawler.alert_operations_format import format_notification_summary
from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction, print_error, print_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show notification operations status.")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--channel", help="Filter by notification channel")
    parser.add_argument("--recent", type=int, default=10, help="Recent failure count")
    parser.add_argument("--failures", action="store_true", help="Show recent failures only")
    args = parser.parse_args(argv)

    try:
        view = build_alert_operations_view()
        summary = view.summarize_notifications(
            channel=args.channel,
            recent_limit=args.recent,
        )
    except Exception as exc:
        print_error(f"Error: {exc}")
        return 1

    if args.json:
        payload = summary.to_dict()
        if args.failures:
            payload = {"recent_failures": payload["recent_failures"]}
        print_json(payload, secrets=collect_secrets_for_redaction())
        return 0

    if args.failures:
        if not summary.recent_failures:
            print("No recent notification failures.")
            return 0
        lines = ["Recent Notification Failures", ""]
        for item in summary.recent_failures:
            lines.append(
                f"{item.get('alert_id', '-')} [{item.get('channel', '-')}] "
                f"{item.get('message', '-')}"
            )
        print("\n".join(lines))
        return 0

    print(format_notification_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
