"""Show current GPU price snapshots for crawl targets."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction, print_error, print_json
from pricebrain_app.crawler.ops_format import format_gpu_price_status, format_price_summary_list
from pricebrain_app.crawler.price_calculations import build_price_snapshot
from pricebrain_app.crawler.price_ops_cli import (
    add_price_filter_arguments,
    build_price_operations_view,
    parse_price_filters,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show GPU price snapshots.")
    add_price_filter_arguments(parser)
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show aggregate GPU price status summary",
    )
    args = parser.parse_args(argv)
    secrets = collect_secrets_for_redaction()

    try:
        view = build_price_operations_view()
        filters = parse_price_filters(args)
        if args.status:
            summary = view.summarize_gpu_prices(filters=filters)
            if args.json:
                print_json(summary.to_dict(), secrets=secrets)
            else:
                print(format_gpu_price_status(summary))
            return 0

        summaries = view.list_price_summaries(filters=filters)
        if args.target_id and len(summaries) == 1:
            snapshot = build_price_snapshot(summaries[0])
            if args.json:
                print_json(snapshot.to_dict(), secrets=secrets)
            else:
                from pricebrain_app.crawler.ops_format import format_price_snapshot

                print(format_price_snapshot(snapshot))
            return 0

        if args.json:
            print_json([item.to_dict() for item in summaries], secrets=secrets)
            return 0

        print(format_price_summary_list(summaries, title="GPU Prices"))
    except Exception as exc:
        print_error(f"Error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
