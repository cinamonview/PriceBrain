"""Pure dashboard health classification — no I/O."""

from __future__ import annotations

from pricebrain_app.crawler.dashboard_operations_models import (
    AlertDashboardSummary,
    AuditDashboardSummary,
    CrawlerDashboardSummary,
    DashboardHealthStatus,
    DashboardSummary,
    NotificationDashboardSummary,
    PriceDashboardSummary,
    RunnerDashboardSummary,
)


def classify_dashboard_health(
    *,
    crawler: CrawlerDashboardSummary,
    price: PriceDashboardSummary,
    alerts: AlertDashboardSummary,
    notifications: NotificationDashboardSummary,
    runner: RunnerDashboardSummary,
    audit: AuditDashboardSummary,
) -> DashboardSummary:
    reasons: list[str] = []
    section_errors = sum(
        1
        for section in (crawler, price, alerts, notifications, runner, audit)
        if section.read_error is not None
    )

    has_data = any(
        [
            crawler.total_targets > 0,
            price.targets > 0,
            alerts.total > 0,
            notifications.sent + notifications.failed + notifications.skipped > 0,
            runner.recent_cycles > 0,
            audit.recent_events > 0,
        ]
    )
    if not has_data and section_errors == 0:
        return DashboardSummary(
            health=DashboardHealthStatus.UNKNOWN,
            reasons=("insufficient dashboard data",),
        )

    if section_errors >= 4:
        reasons.append(f"{section_errors} dashboard sections failed to load")
        return DashboardSummary(health=DashboardHealthStatus.CRITICAL, reasons=tuple(reasons))

    if runner.last_cycle_status == "FAILED" and runner.recent_failed_cycles >= 2:
        reasons.append("repeated runner cycle failures")
        return DashboardSummary(health=DashboardHealthStatus.CRITICAL, reasons=tuple(reasons))

    if notifications.failed > 0:
        reasons.append("notification failures detected")
    if crawler.failed_targets > 0:
        reasons.append(f"{crawler.failed_targets} crawler target failures")
    if crawler.ssg_access_denied > 0:
        reasons.append(f"{crawler.ssg_access_denied} SSG_ACCESS_DENIED targets")
    if alerts.invalid > 0 or alerts.recent_invalid > 0:
        reasons.append("invalid alert evaluations detected")
    if audit.read_error:
        reasons.append("audit read errors detected")
    if runner.last_cycle_status == "FAILED":
        reasons.append("latest runner cycle failed")
    if section_errors > 0:
        reasons.append(f"{section_errors} dashboard section read errors")

    if reasons:
        return DashboardSummary(health=DashboardHealthStatus.DEGRADED, reasons=tuple(reasons))

    if not has_data:
        return DashboardSummary(
            health=DashboardHealthStatus.UNKNOWN,
            reasons=("insufficient dashboard data",),
        )

    return DashboardSummary(health=DashboardHealthStatus.HEALTHY, reasons=())


def runner_cycle_status(
    *,
    last_failed_cycle_at,
    last_successful_cycle_at,
    errors: tuple[str, ...] = (),
    notification_failed: int = 0,
) -> str:
    if last_failed_cycle_at is not None and (
        last_successful_cycle_at is None or last_failed_cycle_at >= last_successful_cycle_at
    ):
        return "FAILED"
    if errors or notification_failed > 0:
        return "FAILED"
    if last_successful_cycle_at is not None or last_failed_cycle_at is not None:
        return "SUCCESS"
    return "UNKNOWN"
