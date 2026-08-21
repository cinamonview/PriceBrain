"""Show upcoming crawler schedule for enabled targets."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.ops_cli import (
    build_operations_view,
    collect_secrets_for_redaction,
    print_error,
    print_json,
)
from pricebrain_app.crawler.ops_format import format_schedule


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show crawler schedule for enabled targets.")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)
    secrets = collect_secrets_for_redaction()

    try:
        view = build_operations_view()
        entries = view.list_schedule()
    except Exception as exc:
        print_error(f"Error: {exc}")
        return 1

    if args.json:
        print_json([entry.to_dict() for entry in entries], secrets=secrets)
        return 0

    print(format_schedule(entries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
