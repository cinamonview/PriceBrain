"""List GPU targets with recent price increases."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction, print_error, print_json
from pricebrain_app.crawler.ops_format import format_price_summary_list
from pricebrain_app.crawler.price_ops_cli import (
    add_price_filter_arguments,
    build_price_operations_view,
    parse_price_filters,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List GPU targets with price increases.")
    add_price_filter_arguments(parser)
    args = parser.parse_args(argv)
    secrets = collect_secrets_for_redaction()

    try:
        view = build_price_operations_view()
        summaries = view.list_price_increases(filters=parse_price_filters(args))
    except Exception as exc:
        print_error(f"Error: {exc}")
        return 1

    if args.json:
        print_json([item.to_dict() for item in summaries], secrets=secrets)
        return 0

    print(format_price_summary_list(summaries, title="GPU Price Increases"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
