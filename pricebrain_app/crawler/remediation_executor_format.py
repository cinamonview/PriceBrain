"""Human-readable remediation execution output."""

from __future__ import annotations

from pricebrain_app.crawler.remediation_executor_models import (
    RemediationExecutionResult,
    RemediationPlanExecutionResult,
)


def format_execution_result(result: RemediationExecutionResult) -> str:
    lines = [
        f"[{result.mode.value}/{result.status.value}] {result.action_type.value}",
        f"Action: {result.action_id}",
        f"Message: {result.message}",
        f"Mutation performed: {str(result.mutation_performed).lower()}",
        f"Approval verified: {str(result.approval_verified).lower()}",
    ]
    if result.error_code:
        lines.append(f"Error code: {result.error_code}")
    return "\n".join(lines)


def format_plan_execution(payload: RemediationPlanExecutionResult) -> str:
    lines = [
        "==================================================",
        "PriceBrain Remediation Execution",
        "==================================================",
        f"Mode: {payload.mode.value}",
        "",
    ]
    if not payload.results:
        lines.append("No execution results.")
    else:
        for result in payload.results:
            lines.append(format_execution_result(result))
            lines.append("")
    lines.append("==================================================")
    return "\n".join(lines).rstrip()
