"""Human-readable remediation plan formatting."""

from __future__ import annotations

from pricebrain_app.crawler.dashboard_operations_format import format_dashboard_timestamp
from pricebrain_app.crawler.remediation_operations_models import RemediationAction, RemediationPlan


def format_remediation_action(action: RemediationAction) -> str:
    lines = [
        f"[{action.priority.value}/{action.risk.value}] {action.action_type.value}",
        f"Finding: {action.finding_id}",
        f"Reason: {action.reason}",
    ]
    if action.target_id:
        lines.append(f"Target: {action.target_id}")
    if action.alert_id:
        lines.append(f"Alert: {action.alert_id}")
    lines.append("Recommended steps:")
    for step in action.recommended_steps:
        lines.append(f"  - {step}")
    lines.append(f"Human approval required: {str(action.human_approval_required).lower()}")
    lines.append(f"Auto executable: {str(action.auto_executable).lower()}")
    if action.read_error:
        lines.append(f"Read error: {action.read_error}")
    return "\n".join(lines)


def format_remediation_plan(plan: RemediationPlan) -> str:
    lines = [
        "==================================================",
        "PriceBrain Remediation Plan",
        "==================================================",
        "",
        f"HEALTH: {plan.health.value}",
        f"Generated: {format_dashboard_timestamp(plan.generated_at)}",
        f"Total findings: {plan.total_findings}",
        f"Actionable findings: {plan.actionable_findings}",
        f"Actions: {plan.summary.actionable_actions}",
        "",
        "Remediation Actions:",
        "",
    ]
    if not plan.actions:
        lines.append("No remediation actions generated.")
    else:
        for action in plan.actions:
            if action.action_type.value == "NO_ACTION":
                continue
            lines.append(format_remediation_action(action))
            lines.append("")
    lines.append("==================================================")
    return "\n".join(lines).rstrip()
