"""Human-readable dashboard output formatting."""

from __future__ import annotations

from datetime import datetime

from pricebrain_app.crawler.dashboard_operations_models import PriceBrainDashboardSnapshot
from pricebrain_app.crawler.targets import utc_now


def format_dashboard_timestamp(value: datetime | None) -> str:
    if value is None:
        return "-"
    if value.tzinfo is None:
        value = value.replace(tzinfo=utc_now().tzinfo)
    return value.strftime("%Y-%m-%d %H:%M:%S UTC")


def format_dashboard(snapshot: PriceBrainDashboardSnapshot) -> str:
    lines = [
        "==================================================",
        "PriceBrain Operations Dashboard",
        "==================================================",
        "",
        "Generated:",
        format_dashboard_timestamp(snapshot.generated_at),
        "",
        f"Overall Health      : {snapshot.summary.health.value}",
    ]
    if snapshot.summary.reasons:
        lines.append(f"Health Reasons      : {', '.join(snapshot.summary.reasons)}")
    lines.extend(
        [
            "",
            "[ CRAWLER ]",
            "",
            f"Targets             : {snapshot.crawler.total_targets}",
            f"Enabled             : {snapshot.crawler.enabled_targets}",
            f"Disabled            : {snapshot.crawler.disabled_targets}",
            f"Failed              : {snapshot.crawler.failed_targets}",
            f"SSG_ACCESS_DENIED   : {snapshot.crawler.ssg_access_denied}",
        ]
    )
    if snapshot.crawler.read_error:
        lines.append(f"Read Error          : {snapshot.crawler.read_error}")
    lines.extend(
        [
            "",
            "[ PRICE ]",
            "",
            f"With Price          : {snapshot.price.with_price}",
            f"Without Price       : {snapshot.price.without_price}",
            f"Price Down          : {snapshot.price.price_down}",
            f"Price Up            : {snapshot.price.price_up}",
            f"No History          : {snapshot.price.no_history}",
        ]
    )
    if snapshot.price.read_error:
        lines.append(f"Read Error          : {snapshot.price.read_error}")
    lines.extend(
        [
            "",
            "[ ALERT ]",
            "",
            f"Total               : {snapshot.alerts.total}",
            f"Enabled             : {snapshot.alerts.enabled}",
            f"Disabled            : {snapshot.alerts.disabled}",
            f"Triggered Recently  : {snapshot.alerts.triggered_recently}",
            f"Never Triggered     : {snapshot.alerts.never_triggered}",
        ]
    )
    if snapshot.alerts.read_error:
        lines.append(f"Read Error          : {snapshot.alerts.read_error}")
    lines.extend(
        [
            "",
            "[ NOTIFICATION ]",
            "",
            f"Sent                : {snapshot.notifications.sent}",
            f"Failed              : {snapshot.notifications.failed}",
            f"Skipped             : {snapshot.notifications.skipped}",
        ]
    )
    if snapshot.notifications.read_error:
        lines.append(f"Read Error          : {snapshot.notifications.read_error}")
    lines.extend(
        [
            "",
            "[ RUNNER ]",
            "",
            f"Last Cycle          : {snapshot.runner.last_cycle_status}",
            f"Last Run            : {format_dashboard_timestamp(snapshot.runner.last_run_at)}",
            f"Duration            : {snapshot.runner.duration_seconds if snapshot.runner.duration_seconds is not None else '-'}",
        ]
    )
    if snapshot.runner.read_error:
        lines.append(f"Read Error          : {snapshot.runner.read_error}")
    lines.extend(
        [
            "",
            "[ AUDIT ]",
            "",
            f"Recent Events       : {snapshot.audit.recent_events}",
            f"Recent Failures     : {snapshot.audit.recent_failures}",
        ]
    )
    if snapshot.audit.read_error:
        lines.append(f"Read Error          : {snapshot.audit.read_error}")
    lines.append("")
    lines.append("==================================================")
    return "\n".join(lines)
