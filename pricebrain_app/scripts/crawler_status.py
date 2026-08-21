"""Print overall crawler operational status."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.metrics import get_crawler_metrics
from pricebrain_app.crawler.ops_cli import (
    build_operations_view,
    collect_secrets_for_redaction,
    print_error,
    print_json,
)
from pricebrain_app.crawler.ops_format import format_status_summary, format_worker_health
from pricebrain_app.crawler.worker_health import get_worker_health


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show PriceBrain crawler operational status.")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)
    secrets = collect_secrets_for_redaction()

    try:
        view = build_operations_view()
        summary = view.summarize()
        malls = view.summarize_by_mall()
    except Exception as exc:
        print_error(f"Error: {exc}")
        return 1

    if args.json:
        payload = view.status_payload()
        print_json(payload, secrets=secrets)
        return 0

    print(format_status_summary(summary, malls))
    print()
    print(format_worker_health(get_worker_health()))
    print()
    print("Metrics:")
    for key, value in get_crawler_metrics().to_dict().items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
