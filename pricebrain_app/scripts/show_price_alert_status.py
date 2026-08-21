"""Show aggregate price alert operations status."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.alert_operations_cli import build_alert_operations_view
from pricebrain_app.crawler.alert_operations_format import format_alert_snapshot_list, format_alert_summary
from pricebrain_app.crawler.alert_operations_models import AlertListFilter
from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction, print_error, print_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show price alert operations status.")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--recent", type=int, help="Show recent alert snapshots")
    parser.add_argument("--type", help="Filter by alert type")
    parser.add_argument("--mall", help="Filter by mall_id")
    args = parser.parse_args(argv)

    filters = AlertListFilter(
        alert_type=args.type,
        mall_id=args.mall,
    )

    try:
        view = build_alert_operations_view()
        summary = view.summarize_alerts(filters=filters)
        if args.recent is not None:
            snapshots = view.list_alert_snapshots(filters=filters)[: max(int(args.recent), 0)]
        else:
            snapshots = []
    except Exception as exc:
        print_error(f"Error: {exc}")
        return 1

    if args.json:
        payload = {"summary": summary.to_dict()}
        if args.recent is not None:
            payload["recent"] = [item.to_dict() for item in snapshots]
        print_json(payload, secrets=collect_secrets_for_redaction())
        return 0

    print(format_alert_summary(summary))
    if args.recent is not None:
        print("")
        print(format_alert_snapshot_list(snapshots))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
