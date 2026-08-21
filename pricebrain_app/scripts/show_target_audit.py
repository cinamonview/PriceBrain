"""Show audit history for a crawl target."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.audit_operations_cli import build_audit_operations_view
from pricebrain_app.crawler.audit_operations_format import format_audit_event_list
from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction, print_error, print_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show target audit history.")
    parser.add_argument("--target-id", required=True, help="Crawl target ID")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    try:
        view = build_audit_operations_view()
        events = view.list_target_audit(args.target_id.strip())
    except Exception as exc:
        print_error(f"Error: {exc}")
        return 1

    if args.json:
        print_json(
            {"target_id": args.target_id.strip(), "events": [item.to_dict() for item in events]},
            secrets=collect_secrets_for_redaction(),
        )
        return 0

    print(format_audit_event_list(events, title=f"Target Audit: {args.target_id.strip()}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
