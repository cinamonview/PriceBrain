"""Show price history for a crawl target."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction, print_error, print_json
from pricebrain_app.crawler.ops_format import format_price_history
from pricebrain_app.crawler.price_ops_cli import build_price_operations_view


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show price history for a crawl target.")
    parser.add_argument("--target-id", required=True, help="Crawl target ID")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)
    secrets = collect_secrets_for_redaction()

    try:
        view = build_price_operations_view()
        target_id = args.target_id.strip()
        summary = view.get_price_summary(target_id)
        if summary is None:
            print_error(f"Target not found: crawler_targets/{target_id}")
            return 1
        history = view.get_price_history(target_id)
    except Exception as exc:
        print_error(f"Error: {exc}")
        return 1

    if args.json:
        payload = {
            "target_id": target_id,
            "summary": summary.to_dict(),
            "history": [entry.to_dict() for entry in history],
        }
        print_json(payload, secrets=secrets)
        return 0

    print(format_price_history(history))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
