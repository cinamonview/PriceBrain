"""Evaluate enabled price alerts against latest price snapshots."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction, print_json
from pricebrain_app.crawler.price_alert_cli import build_price_alert_service


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate enabled price alerts.")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    try:
        service = build_price_alert_service()
        results, summary = service.check_enabled_alerts()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    payload = {
        "summary": summary.to_dict(),
        "results": [item.to_dict() for item in results],
    }
    if args.json:
        print_json(payload, secrets=collect_secrets_for_redaction())
        return 0

    print(format_check_results(summary, results))
    return 0


def format_check_results(summary, results) -> str:
    lines = [
        "Price Alert Check",
        "",
        f"total: {summary.total}",
        f"triggered: {summary.triggered}",
        f"not_triggered: {summary.not_triggered}",
        f"skipped: {summary.skipped}",
        f"invalid: {summary.invalid}",
        f"failed: {summary.failed}",
    ]
    if results:
        lines.extend(["", "Results:"])
        for item in results:
            lines.append(
                f"  {item.alert_id} [{item.outcome.value}] "
                f"target={item.target_id} current={item.current_price or '-'}"
            )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
