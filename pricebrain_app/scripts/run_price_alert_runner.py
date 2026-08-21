"""Run the price alert evaluation and notification runner."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction, print_error, print_json
from pricebrain_app.crawler.price_alert_runner_cli import build_price_alert_runner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run price alert evaluation cycles.")
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    parser.add_argument(
        "--interval",
        type=float,
        help="Polling interval in seconds for continuous mode",
    )
    parser.add_argument(
        "--max-alerts",
        type=int,
        help="Maximum number of enabled alerts to evaluate per cycle",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate alerts without state mutation or notification dispatch",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    if not args.once and args.interval is None:
        parser.error("Specify --once or provide --interval for continuous mode")

    try:
        runner = build_price_alert_runner(interval_seconds=args.interval)
        if args.once:
            result = runner.run_once(
                dry_run=args.dry_run,
                max_alerts=args.max_alerts,
            )
        else:
            result = runner.run_forever(
                dry_run=args.dry_run,
                max_alerts=args.max_alerts,
                interval_seconds=args.interval,
            )
    except Exception as exc:
        print_error(f"Error: {exc}")
        return 1

    if args.json:
        print_json(result.to_dict(), secrets=collect_secrets_for_redaction())
        return 0

    print(format_cycle_result(result))
    return 0


def format_cycle_result(result) -> str:
    return "\n".join(
        [
            "Price Alert Runner",
            "",
            f"total_alerts: {result.total_alerts}",
            f"evaluated: {result.evaluated}",
            f"triggered: {result.triggered}",
            f"skipped: {result.skipped}",
            f"invalid: {result.invalid}",
            f"not_triggered: {result.not_triggered}",
            f"notification_sent: {result.notification_sent}",
            f"notification_failed: {result.notification_failed}",
            f"dry_run: {str(result.dry_run).lower()}",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
