"""Show price analysis and purchase verdicts for stored products (read-only).

Run against real data (GOOGLE_APPLICATION_CREDENTIALS) or the emulator
(FIRESTORE_EMULATOR_HOST) to check verdicts before tuning purchase rules:

    python -m pricebrain_app.scripts.show_price_analysis --window-days 30 --sensitivity
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Any

from pricebrain_app.analysis.models import DEFAULT_WINDOW_DAYS, SUPPORTED_WINDOW_DAYS
from pricebrain_app.analysis.product_analysis import analyze_product
from pricebrain_app.analysis.report import format_report, format_sensitivity, sensitivity
from pricebrain_app.repository.price_analysis_repository import PriceAnalysisRepository

PRODUCT_LIMIT = 200


def run(
    db: Any,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    product_id: str | None = None,
    show_sensitivity: bool = False,
    now: datetime | None = None,
) -> str:
    now = now or datetime.now(timezone.utc)
    repository = PriceAnalysisRepository(db)
    if product_id:
        product = repository.get_product(product_id)
        rows = [(product_id, product or {})]
    else:
        rows = repository.list_products(limit=PRODUCT_LIMIT)

    analyses = [
        analyze_product(
            product_id=pid,
            product_name=data.get("normalized_product_name"),
            listings=repository.list_listing_histories(pid),
            window_days=window_days,
            now=now,
        )
        for pid, data in rows
    ]
    sections = [format_report(analyses)]
    if show_sensitivity and analyses:
        sections.append(format_sensitivity(sensitivity(analyses, now=now), total=len(analyses)))
    return "\n\n".join(sections)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show price analysis and purchase verdicts.")
    parser.add_argument("--window-days", type=int, choices=SUPPORTED_WINDOW_DAYS, default=DEFAULT_WINDOW_DAYS)
    parser.add_argument("--product-id", help="Analyze a single product")
    parser.add_argument("--sensitivity", action="store_true", help="Show verdict counts per threshold")
    args = parser.parse_args(argv)

    from pricebrain_app.firebase.admin import get_firestore_client

    try:
        db = get_firestore_client()
        print(
            run(
                db,
                window_days=args.window_days,
                product_id=args.product_id,
                show_sensitivity=args.sensitivity,
            )
        )
    except Exception as exc:  # CLI boundary: report and exit non-zero
        print(f"Error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
