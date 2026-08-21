"""Show PriceBrain remediation action plan."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.dashboard_operations_models import DashboardFilter
from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction, print_error, print_json
from pricebrain_app.crawler.remediation_operations_cli import build_remediation_operations_view
from pricebrain_app.crawler.remediation_operations_format import format_remediation_plan
from pricebrain_app.crawler.remediation_operations_models import RemediationFilter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show PriceBrain remediation action plan.")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--failures", action="store_true", help="Show actionable remediation only")
    parser.add_argument("--priority", help="Filter by priority (low/medium/high/critical)")
    parser.add_argument("--area", help="Filter by area")
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
    remediation_filters = RemediationFilter(
        area=args.area.lower() if args.area else None,
        target_id=args.target_id,
        alert_id=args.alert_id,
        priority=args.priority,
        failures_only=args.failures,
    )

    try:
        view = build_remediation_operations_view()
        plan = view.build_remediation_plan(dashboard_filters=dashboard_filters)
        actions = view.actions(filters=remediation_filters, plan=plan)
    except Exception as exc:
        print_error(f"Error: {exc}")
        return 1

    if args.json:
        payload = plan.to_dict()
        payload["actions"] = [item.to_dict() for item in actions]
        print_json(payload, secrets=collect_secrets_for_redaction())
        return 0

    filtered_plan = type(plan)(
        generated_at=plan.generated_at,
        health=plan.health,
        total_findings=plan.total_findings,
        actionable_findings=plan.actionable_findings,
        actions=tuple(actions),
        read_errors=plan.read_errors,
        summary=plan.summary,
    )
    print(format_remediation_plan(filtered_plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
