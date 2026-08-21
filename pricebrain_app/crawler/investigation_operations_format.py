"""Human-readable investigation output formatting."""

from __future__ import annotations

from pricebrain_app.crawler.dashboard_operations_format import format_dashboard_timestamp
from pricebrain_app.crawler.investigation_operations_models import (
    DashboardInvestigationSnapshot,
    InvestigationFinding,
)


def format_investigation_finding(item: InvestigationFinding) -> str:
    lines = [
        f"[{item.severity.value}] {item.code}",
        item.message,
    ]
    if item.target_id:
        lines.append(f"target={item.target_id}")
    if item.alert_id:
        lines.append(f"alert={item.alert_id}")
    return "\n".join(lines)


def format_investigation(snapshot: DashboardInvestigationSnapshot) -> str:
    lines = [
        "==================================================",
        "PriceBrain Dashboard Investigation",
        "==================================================",
        "",
        f"HEALTH: {snapshot.health.value}",
        f"Generated: {format_dashboard_timestamp(snapshot.generated_at)}",
        "",
    ]
    if snapshot.dashboard_summary.reasons:
        lines.append("Dashboard Reasons:")
        for reason in snapshot.dashboard_summary.reasons:
            lines.append(f"  - {reason}")
        lines.append("")

    lines.extend(
        [
            "Findings:",
            "",
        ]
    )
    if not snapshot.findings:
        lines.append("No investigation findings.")
    else:
        for item in snapshot.findings:
            lines.append(format_investigation_finding(item))
            lines.append("")

    lines.append("==================================================")
    return "\n".join(lines).rstrip()
