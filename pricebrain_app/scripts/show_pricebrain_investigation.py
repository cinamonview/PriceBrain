"""Show PriceBrain dashboard investigation findings."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.dashboard_operations_models import DashboardFilter
from pricebrain_app.crawler.investigation_operations_cli import build_investigation_operations_view
from pricebrain_app.crawler.investigation_operations_format import format_investigation
from pricebrain_app.crawler.investigation_operations_models import InvestigationFilter
from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction, print_error, print_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Investigate PriceBrain dashboard health.")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--failures", action="store_true", help="Show non-info findings only")
    parser.add_argument("--area", help="Filter by investigation area")
    parser.add_argument("--target-id", help="Filter by target ID")
    parser.add_argument("--alert-id", help="Filter by alert ID")
    parser.add_argument("--recent", type=int, default=10, help="Recent dashboard window")
    parser.add_argument("--mall", help="Filter dashboard by mall_id")
    parser.add_argument("--category", default="gpu", help="Filter dashboard by category")
    parser.add_argument("--tag", help="Filter dashboard by tag")
    args = parser.parse_args(argv)

    dashboard_filters = DashboardFilter(
        mall_id=args.mall,
        category=args.category,
        tag=args.tag,
        recent=max(int(args.recent), 1),
        failures_only=args.failures,
    )
    investigation_filters = InvestigationFilter(
        area=args.area.lower() if args.area else None,
        target_id=args.target_id,
        alert_id=args.alert_id,
        failures_only=args.failures,
    )

    try:
        view = build_investigation_operations_view()
        snapshot = view.investigate_dashboard(dashboard_filters=dashboard_filters)
        findings = view.findings(filters=investigation_filters, snapshot=snapshot)
        summary = view.summary(filters=investigation_filters, snapshot=snapshot)
    except Exception as exc:
        print_error(f"Error: {exc}")
        return 1

    if args.json:
        payload = snapshot.to_dict()
        payload["findings"] = [item.to_dict() for item in findings]
        payload["summary"] = summary.to_dict()
        print_json(payload, secrets=collect_secrets_for_redaction())
        return 0

    filtered_snapshot = type(snapshot)(
        generated_at=snapshot.generated_at,
        health=snapshot.health,
        summary=summary,
        findings=tuple(findings),
        dashboard_summary=snapshot.dashboard_summary,
        crawler=snapshot.crawler,
        price=snapshot.price,
        alerts=snapshot.alerts,
        notifications=snapshot.notifications,
        runner=snapshot.runner,
        audit=snapshot.audit,
    )
    print(format_investigation(filtered_snapshot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
