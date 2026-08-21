"""Create a price alert rule for a crawl target."""

from __future__ import annotations

import argparse
import json
import sys

from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction, print_json
from pricebrain_app.crawler.price_alert_cli import build_price_alert_repository, build_target_repository
from pricebrain_app.crawler.price_alert_models import parse_cli_alert_type


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a price alert for a crawl target.")
    parser.add_argument("--target-id", required=True, help="Crawl target ID")
    parser.add_argument(
        "--type",
        required=True,
        help="Alert type: price-below, price-drop-percent, price-drop-amount, price-up, price-changed",
    )
    parser.add_argument("--threshold", type=float, required=True, help="Alert threshold")
    parser.add_argument("--cooldown-seconds", type=int, default=0, help="Optional duplicate cooldown")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    try:
        target_repo = build_target_repository()
        target = target_repo.get(args.target_id.strip())
        if target is None:
            print(f"Error: target not found: {args.target_id}", file=sys.stderr)
            return 1

        alert_type = parse_cli_alert_type(args.type)
        alert_repo = build_price_alert_repository()
        alert = alert_repo.create(
            target_id=target.target_id,
            mall_id=target.mall_id,
            alert_type=alert_type,
            threshold=args.threshold,
            product_name=target.product_name,
            brand=target.tags[0] if target.tags else None,
            cooldown_seconds=args.cooldown_seconds,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    payload = alert.to_firestore_dict()
    if args.json:
        print_json(payload, secrets=collect_secrets_for_redaction())
    else:
        print(format_created_alert(alert.alert_id, payload))
    return 0


def format_created_alert(alert_id: str, payload: dict) -> str:
    return "\n".join(
        [
            "Price Alert Created",
            "",
            f"alert_id: {alert_id}",
            f"target_id: {payload.get('target_id')}",
            f"type: {payload.get('alert_type')}",
            f"threshold: {payload.get('threshold')}",
            f"enabled: {str(payload.get('enabled')).lower()}",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
