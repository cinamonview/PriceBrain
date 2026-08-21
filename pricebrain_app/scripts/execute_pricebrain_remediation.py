"""Execute PriceBrain remediation actions under human approval boundaries."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.dashboard_operations_models import DashboardFilter
from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction, print_error, print_json
from pricebrain_app.crawler.remediation_executor_cli import build_remediation_executor_view
from pricebrain_app.crawler.remediation_executor_format import format_plan_execution
from pricebrain_app.crawler.remediation_executor_models import RemediationExecutionMode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Execute PriceBrain remediation actions.")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--preview", action="store_true", help="Preview planned execution")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run handler verification")
    parser.add_argument("--execute", action="store_true", help="Execute with approval token")
    parser.add_argument("--action-id", help="Remediation action ID")
    parser.add_argument("--approval-token", help="Human approval token")
    parser.add_argument("--recent", type=int, default=10, help="Recent dashboard window")
    parser.add_argument("--mall", help="Filter dashboard by mall_id")
    parser.add_argument("--category", default="gpu", help="Filter dashboard by category")
    parser.add_argument("--tag", help="Filter dashboard by tag")
    args = parser.parse_args(argv)

    if args.execute and not args.action_id:
        print_error("Error: --execute requires --action-id")
        return 1
    if args.execute and not args.approval_token:
        print_error("Error: --execute requires --approval-token")
        return 1

    dashboard_filters = DashboardFilter(
        mall_id=args.mall,
        category=args.category,
        tag=args.tag,
        recent=max(int(args.recent), 1),
    )

    try:
        view = build_remediation_executor_view()
        plan = view.build_plan(dashboard_filters=dashboard_filters)
        if args.execute:
            action = view.get_action(plan, args.action_id or "")
            if action is None:
                print_error(f"Action not found: {args.action_id}")
                return 1
            result = view.execute(action, approval_token=args.approval_token)
            payload = {"result": result.to_dict()}
        elif args.dry_run:
            execution = view.execute_plan(plan, mode=RemediationExecutionMode.DRY_RUN)
            payload = execution.to_dict()
        else:
            mode = RemediationExecutionMode.PLAN
            execution = view.execute_plan(plan, mode=mode)
            payload = execution.to_dict()
    except Exception as exc:
        print_error(f"Error: {exc}")
        return 1

    if args.json:
        print_json(payload, secrets=collect_secrets_for_redaction())
        return 0

    if args.execute:
        from pricebrain_app.crawler.remediation_executor_format import format_execution_result

        print(format_execution_result(result))
        return 0

    print(format_plan_execution(execution))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
