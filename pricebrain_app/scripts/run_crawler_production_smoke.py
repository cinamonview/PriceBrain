"""Production-like local smoke CLI — single Firestore target via Worker path."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.config.settings import get_settings
from pricebrain_app.crawler.logging_utils import redact_secrets
from pricebrain_app.crawler.production_smoke import (
    SmokeConfig,
    SmokeExitCode,
    load_target_preview,
    print_startup_target_info,
    render_smoke_outcome,
    run_smoke,
)
from pricebrain_app.firebase.admin import get_firestore_client


def _collect_secrets_for_redaction() -> list[str]:
    settings = get_settings()
    secrets: list[str] = []
    if settings.pricebrain_ingest_api_key:
        secrets.append(settings.pricebrain_ingest_api_key)
    if settings.google_application_credentials:
        secrets.append(settings.google_application_credentials)
    return secrets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a production-like crawler smoke test for one Firestore crawl target. "
            "Default: crawl only (dry-run, no ingest)."
        ),
    )
    parser.add_argument(
        "--target-id",
        required=True,
        help="crawler_targets document ID to validate (required)",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="POST successful crawls to /internal/ingest/listing",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Crawl without ingest (default)",
    )
    parser.add_argument(
        "--verify-firestore",
        action="store_true",
        help="Print before/after Firestore target snapshots",
    )
    parser.add_argument(
        "--verify-product",
        action="store_true",
        help="After successful ingest, verify products/{product_id} exists",
    )
    parser.add_argument(
        "--verify-listing",
        action="store_true",
        help="After successful ingest, verify listings/{listing_id} exists",
    )
    parser.add_argument(
        "--verify-price-history",
        action="store_true",
        help="After successful ingest, verify listing price_history documents",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print smoke result as JSON",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Override PRICEBRAIN_CRAWLER_TIMEOUT_SECONDS",
    )
    parser.add_argument(
        "--lease-seconds",
        type=int,
        default=None,
        help="Override PRICEBRAIN_CRAWLER_LEASE_SECONDS for this smoke run",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ingest = bool(args.ingest)
    if ingest:
        _ = args.dry_run  # --ingest explicitly opts out of dry-run

    secrets = _collect_secrets_for_redaction()
    config = SmokeConfig(
        target_id=args.target_id.strip(),
        ingest=ingest,
        verify_firestore=args.verify_firestore,
        verify_product=args.verify_product,
        verify_listing=args.verify_listing,
        verify_price_history=args.verify_price_history,
        json_output=args.json,
        timeout=args.timeout,
        lease_seconds=args.lease_seconds,
    )

    try:
        db = get_firestore_client()
        target = load_target_preview(db, config.target_id)
        if target is not None and not config.json_output:
            preview = print_startup_target_info(target)
            print(redact_secrets(preview, secrets))
            print()

        outcome = run_smoke(config, db_factory=lambda: db)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return int(SmokeExitCode.ERROR)

    output = render_smoke_outcome(
        outcome,
        verify_firestore=config.verify_firestore,
        json_output=config.json_output,
        secrets=secrets,
    )
    if output:
        print(output)

    if outcome.message and outcome.exit_code != SmokeExitCode.SUCCESS and config.json_output:
        print(
            redact_secrets(
                render_smoke_outcome(
                    outcome,
                    verify_firestore=False,
                    json_output=True,
                    secrets=secrets,
                ),
                secrets,
            )
        )

    return int(outcome.exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
