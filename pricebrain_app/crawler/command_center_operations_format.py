"""Human-readable operations command center output."""

from __future__ import annotations

from pricebrain_app.crawler.command_center_operations_models import CommandCenterSnapshot


def format_command_center(snapshot: CommandCenterSnapshot) -> str:
    dashboard = snapshot.dashboard.get("summary", {})
    investigation = snapshot.investigation.get("summary", {})
    remediation = snapshot.remediation.get("summary", {})
    execution = snapshot.execution.get("summary", {})
    health = snapshot.health
    lines = [
        "==================================================",
        "PriceBrain Operations Command Center",
        "==================================================",
        f"Generated: {snapshot.generated_at.isoformat()}",
        "",
        f"Dashboard health: {health.get('dashboard', 'UNKNOWN')}",
        f"Execution health: {health.get('execution', 'UNKNOWN')}",
        "",
        "Dashboard",
        f"  crawler targets: {snapshot.dashboard.get('crawler', {}).get('total_targets', 0)}",
        f"  price targets: {snapshot.dashboard.get('price', {}).get('targets', 0)}",
        f"  alerts: {snapshot.dashboard.get('alerts', {}).get('total', 0)}",
        "",
        "Investigation",
        f"  findings: {investigation.get('total_findings', 0)}",
        f"  critical: {investigation.get('critical_count', 0)}",
        "",
        "Remediation",
        f"  actions: {remediation.get('total_actions', 0)}",
        f"  actionable: {remediation.get('actionable_actions', 0)}",
        "",
        "Execution History",
        f"  total: {execution.get('total', 0)}",
        f"  executed: {execution.get('executed', 0)}",
        f"  blocked: {execution.get('blocked', 0)}",
        f"  failed: {execution.get('failed', 0)}",
        "==================================================",
    ]
    return "\n".join(lines)
