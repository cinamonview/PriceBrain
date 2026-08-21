"""Format crawler operations output for CLI."""

from __future__ import annotations

from datetime import datetime

from pricebrain_app.crawler.ops_models import (
    CrawlerFailureView,
    CrawlerOpsSummary,
    MallOpsSummary,
    PriceChangeView,
    ScheduleEntry,
    TargetOperationalView,
    WorkerHealthSnapshot,
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


def format_status_summary(summary: CrawlerOpsSummary, malls: list[MallOpsSummary]) -> str:
    lines = [
        "PriceBrain Crawler Status",
        "",
        f"Targets: {summary.total_targets}",
        f"Enabled: {summary.enabled_targets}",
        f"Disabled: {summary.disabled_targets}",
        f"Due: {summary.due_targets}",
        f"Active leases: {summary.lease_active_targets}",
        "",
        f"Success: {summary.success_targets}",
        f"Failed: {summary.failed_targets}",
    ]
    if malls:
        lines.extend(["", "By mall:"])
        for mall in malls:
            lines.append(
                f"  {mall.mall_id.upper()}: total={mall.total} enabled={mall.enabled} "
                f"due={mall.due} success={mall.success} failed={mall.failed}"
            )
    return "\n".join(lines)


def format_target_list(targets: list[TargetOperationalView]) -> str:
    if not targets:
        return "No crawl targets found."
    lines = ["Crawl Targets", ""]
    for target in targets:
        status = target.last_status or "-"
        catalog = ""
        if target.category or target.tags:
            tag_text = ",".join(target.tags) if target.tags else "-"
            catalog = f" category={target.category or '-'} tags={tag_text}"
        lines.append(
            f"{target.target_id} [{target.operational_state}] mall={target.mall_id} "
            f"last={status} next={_fmt_dt(target.next_crawl_at)}{catalog}"
        )
    return "\n".join(lines)


def format_failure_list(failures: list[CrawlerFailureView]) -> str:
    if not failures:
        return "No recent crawler failures."
    lines = ["Recent Crawler Failures", ""]
    for item in failures:
        lines.extend(
            [
                f"{item.target_id} ({item.mall_id})",
                f"  status: {item.last_status or '-'}",
                f"  error: {item.last_error_code or item.last_error_message or '-'}",
                f"  last crawl: {_fmt_dt(item.last_crawled_at)}",
                f"  next crawl: {_fmt_dt(item.next_crawl_at)}",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def format_target_detail(
    target: TargetOperationalView,
    *,
    price_view: PriceChangeView | None = None,
) -> str:
    lease = "idle"
    if target.has_active_lease:
        lease = f"claimed by {target.lease_owner or 'unknown'}"
        if target.lease_until is not None:
            lease += f" until {_fmt_dt(target.lease_until)}"

    lines = [
        f"Target: {target.target_id}",
        f"Mall: {target.mall_id}",
        f"Enabled: {str(target.enabled).lower()}",
        "",
        "URL:",
        target.product_url,
        "",
        f"Interval: {target.crawl_interval_seconds} sec",
        f"Priority: {target.priority}",
        "",
        "Catalog:",
        f"  name: {target.product_name or '-'}",
        f"  category: {target.category or '-'}",
        f"  tags: {', '.join(target.tags) if target.tags else '-'}",
        "",
        "Last crawl:",
        _fmt_dt(target.last_crawled_at),
        "",
        "Last status:",
        target.last_status or "-",
        "",
        "Error:",
        target.last_error_code or target.last_error_message or "-",
        "",
        "Last price:",
        _fmt_price(target.last_crawled_price),
        "",
        "Next crawl:",
        _fmt_dt(target.next_crawl_at),
        "",
        "Lease:",
        lease,
    ]
    if price_view is not None:
        lines.extend(
            [
                "",
                "Price history:",
                f"  product: {price_view.product_name or '-'}",
                f"  current: {_fmt_price(price_view.current_price)}",
                f"  previous: {_fmt_price(price_view.previous_price)}",
                f"  change: {_fmt_price(price_view.price_change)}",
            ]
        )
    return "\n".join(lines)


def format_schedule(entries: list[ScheduleEntry]) -> str:
    if not entries:
        return "Crawler Schedule\n\nNo enabled targets."
    lines = ["Crawler Schedule", ""]
    for entry in entries:
        if entry.is_due:
            timing = "DUE"
        elif entry.seconds_until_due is not None:
            minutes = max(entry.seconds_until_due // 60, 0)
            timing = f"in: {minutes} minutes"
        else:
            timing = "unknown"
        lines.extend(
            [
                entry.target_id,
                f"next crawl: {_fmt_dt(entry.next_crawl_at)}",
                timing,
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def format_worker_health(health: WorkerHealthSnapshot) -> str:
    return "\n".join(
        [
            "Worker Health",
            "",
            f"worker_enabled: {str(health.worker_enabled).lower()}",
            f"last_cycle_started_at: {_fmt_dt(health.last_cycle_started_at)}",
            f"last_cycle_finished_at: {_fmt_dt(health.last_cycle_finished_at)}",
            f"last_cycle_total: {health.last_cycle_total}",
            f"last_cycle_success: {health.last_cycle_success}",
            f"last_cycle_failed: {health.last_cycle_failed}",
            f"last_cycle_error: {health.last_cycle_error or '-'}",
        ]
    )
