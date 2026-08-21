"""List audit events with optional filters."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.audit_operations_cli import build_audit_operations_view
from pricebrain_app.crawler.audit_operations_format import format_audit_event_list
from pricebrain_app.crawler.audit_operations_models import AuditEventFilter
from pricebrain_app.crawler.audit_operations_view import parse_cli_datetime
from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction, print_error, print_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List audit events.")
    parser.add_argument("--event-type", help="Filter by audit event type")
    parser.add_argument("--alert-id", help="Filter by alert ID")
    parser.add_argument("--target-id", help="Filter by target ID")
    parser.add_argument("--mall", help="Filter by mall_id")
    parser.add_argument("--status", help="Filter by status")
    parser.add_argument("--channel", help="Filter by notification channel")
    parser.add_argument("--recent", type=int, help="Limit to recent N events")
    parser.add_argument("--since", help="Include events at or after this ISO datetime")
    parser.add_argument("--until", help="Include events at or before this ISO datetime")
    parser.add_argument("--failures", action="store_true", help="Show failure events only")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    try:
        filters = AuditEventFilter(
            event_type=args.event_type,
            alert_id=args.alert_id,
            target_id=args.target_id,
            mall_id=args.mall,
            status=args.status,
            channel=args.channel,
            failures_only=args.failures,
            since=parse_cli_datetime(args.since) if args.since else None,
            until=parse_cli_datetime(args.until) if args.until else None,
            recent=args.recent,
        )
        view = build_audit_operations_view()
        events = view.list_events(filters=filters)
        summary = view.summarize_events(filters=filters)
    except Exception as exc:
        print_error(f"Error: {exc}")
        return 1

    if args.json:
        print_json(
            {
                "summary": summary.to_dict(),
                "events": [item.to_dict() for item in events],
            },
            secrets=collect_secrets_for_redaction(),
        )
        return 0

    print(format_audit_event_list(events, title="Audit Events"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
