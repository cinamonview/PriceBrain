"""Pure execution history health classification — no I/O."""

from __future__ import annotations

from pricebrain_app.crawler.execution_operations_models import ExecutionHealthStatus, ExecutionHistorySummary


def classify_execution_health(summary: ExecutionHistorySummary) -> tuple[ExecutionHealthStatus, tuple[str, ...]]:
    if summary.total == 0 and summary.read_errors == 0:
        return ExecutionHealthStatus.UNKNOWN, ("no execution history",)

    reasons: list[str] = []

    if summary.read_errors >= 3:
        reasons.append(f"{summary.read_errors} execution history read errors")
        return ExecutionHealthStatus.CRITICAL, tuple(reasons)

    if summary.failed >= 2:
        reasons.append("repeated execution failures")
        return ExecutionHealthStatus.CRITICAL, tuple(reasons)

    if summary.approval_failures >= 2:
        reasons.append("repeated approval boundary failures")
        return ExecutionHealthStatus.CRITICAL, tuple(reasons)

    if summary.failed >= 1:
        reasons.append("recent execution failure")
    if summary.blocked >= 1:
        reasons.append("recent blocked execution")
    if summary.approval_failures >= 1:
        reasons.append("recent approval boundary failure")
    if summary.read_errors >= 1:
        reasons.append(f"{summary.read_errors} execution history read errors")

    if reasons:
        return ExecutionHealthStatus.DEGRADED, tuple(reasons)

    if summary.total == 0:
        return ExecutionHealthStatus.UNKNOWN, ("no execution history",)

    return ExecutionHealthStatus.HEALTHY, ()
