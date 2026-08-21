"""Format alert operations CLI output."""

from __future__ import annotations

from datetime import datetime

from pricebrain_app.crawler.alert_operations_models import (
    AlertSnapshot,
    AlertSummary,
    NotificationOpsSummary,
    RunnerHealthView,
)
from pricebrain_app.crawler.targets import utc_now


def _fmt_dt(value: datetime | None) -> str:
    if value is None:
        return "-"
    if value.tzinfo is None:
        value = value.replace(tzinfo=utc_now().tzinfo)
    return value.strftime("%Y-%m-%d %H:%M:%S UTC")


def _fmt_price(value: int | None) -> str:
    if value is None:
        return "-"
    return f"{value:,}"


def format_alert_summary(summary: AlertSummary) -> str:
    lines = [
        "Price Alert Status",
        "",
        f"total: {summary.total}",
        f"enabled: {summary.enabled}",
        f"disabled: {summary.disabled}",
        f"triggered_recently: {summary.triggered_recently}",
        f"never_triggered: {summary.never_triggered}",
        f"invalid: {summary.invalid}",
        f"read_errors: {summary.read_errors}",
    ]
    if summary.by_type:
        lines.extend(["", "by_type:"])
        for label, count in summary.by_type:
            lines.append(f"  {label}: {count}")
    if summary.by_mall:
        lines.extend(["", "by_mall:"])
        for label, count in summary.by_mall:
            lines.append(f"  {label}: {count}")
    return "\n".join(lines)


def format_alert_snapshot(snapshot: AlertSnapshot) -> str:
    lines = [
        f"Alert: {snapshot.alert_id}",
        f"Target: {snapshot.target_id}",
        f"Type: {snapshot.alert_type}",
        f"Threshold: {snapshot.threshold}",
        f"Enabled: {str(snapshot.enabled).lower()}",
        "",
        f"Current price: {_fmt_price(snapshot.current_price)}",
        f"Previous price: {_fmt_price(snapshot.previous_price)}",
        f"Classification: {snapshot.classification or '-'}",
        f"Last triggered: {_fmt_dt(snapshot.last_triggered_at)}",
        f"Last observed price: {_fmt_price(snapshot.last_observed_price)}",
    ]
    if snapshot.read_error:
        lines.append(f"Read error: {snapshot.read_error}")
    return "\n".join(lines)


def format_alert_snapshot_list(snapshots: list[AlertSnapshot]) -> str:
    if not snapshots:
        return "No alert snapshots found."
    lines = ["Price Alert Snapshots", ""]
    for item in snapshots:
        lines.extend(
            [
                f"{item.alert_id} [{item.alert_type}] target={item.target_id}",
                f"  enabled={str(item.enabled).lower()} current={_fmt_price(item.current_price)} "
                f"classification={item.classification or '-'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def format_notification_summary(summary: NotificationOpsSummary) -> str:
    lines = [
        "Notification Status",
        "",
        f"total_evaluated: {summary.total_evaluated}",
        f"notification_sent: {summary.notification_sent}",
        f"notification_failed: {summary.notification_failed}",
        f"notification_skipped: {summary.notification_skipped}",
    ]
    if summary.by_channel:
        lines.extend(["", "by_channel:"])
        for label, count in summary.by_channel:
            lines.append(f"  {label}: {count}")
    if summary.recent_failures:
        lines.extend(["", "recent_failures:"])
        for item in summary.recent_failures:
            lines.append(
                f"  {item.get('alert_id', '-')} [{item.get('channel', '-')}] "
                f"{item.get('message', '-')}"
            )
    return "\n".join(lines)


def format_runner_health(health: RunnerHealthView) -> str:
    return "\n".join(
        [
            "Price Alert Runner Health",
            "",
            f"last_cycle_started_at: {_fmt_dt(health.last_cycle_started_at)}",
            f"last_cycle_finished_at: {_fmt_dt(health.last_cycle_finished_at)}",
            f"duration_seconds: {health.duration_seconds if health.duration_seconds is not None else '-'}",
            f"total_alerts: {health.total_alerts}",
            f"evaluated: {health.evaluated}",
            f"triggered: {health.triggered}",
            f"skipped: {health.skipped}",
            f"invalid: {health.invalid}",
            f"notification_sent: {health.notification_sent}",
            f"notification_failed: {health.notification_failed}",
            f"last_successful_cycle_at: {_fmt_dt(health.last_successful_cycle_at)}",
            f"last_failed_cycle_at: {_fmt_dt(health.last_failed_cycle_at)}",
        ]
    )
