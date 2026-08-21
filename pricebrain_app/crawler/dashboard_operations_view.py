"""Read-only PriceBrain operations dashboard aggregation."""

from __future__ import annotations

from datetime import datetime

from pricebrain_app.crawler.alert_operations_models import AlertListFilter
from pricebrain_app.crawler.alert_operations_view import AlertOperationsView
from pricebrain_app.crawler.audit_operations_models import AuditEventFilter, AuditEventType
from pricebrain_app.crawler.audit_operations_view import AuditOperationsView
from pricebrain_app.crawler.dashboard_health import classify_dashboard_health, runner_cycle_status
from pricebrain_app.crawler.dashboard_operations_models import (
    AlertDashboardSummary,
    AuditDashboardSummary,
    CrawlerDashboardSummary,
    DashboardFilter,
    NotificationDashboardSummary,
    PriceBrainDashboardSnapshot,
    PriceDashboardSummary,
    RunnerDashboardSummary,
)
from pricebrain_app.crawler.logging_utils import get_crawler_logger
from pricebrain_app.crawler.operations_view import CrawlerOperationsView, TargetListFilter
from pricebrain_app.crawler.price_operations_view import PriceListFilter, PriceOperationsView, price_filter_from_target_filter
from pricebrain_app.crawler.targets import utc_now

logger = get_crawler_logger("crawler.dashboard_operations")
SSG_DENIED_CODES = frozenset({"SSG_ACCESS_DENIED", "ACCESS_DENIED"})
HIGH_PRIORITY_THRESHOLD = 100


class DashboardOperationsView:
    """Compose existing read-only operations views into one dashboard snapshot."""

    def __init__(
        self,
        crawler_view: CrawlerOperationsView,
        price_view: PriceOperationsView,
        alert_view: AlertOperationsView,
        audit_view: AuditOperationsView,
    ) -> None:
        self._crawler = crawler_view
        self._price = price_view
        self._alert = alert_view
        self._audit = audit_view

    def build_dashboard_snapshot(
        self,
        *,
        filters: DashboardFilter | None = None,
        now: datetime | None = None,
    ) -> PriceBrainDashboardSnapshot:
        run_at = now or utc_now()
        flt = filters or DashboardFilter()
        crawler = self._build_crawler(flt, now=run_at)
        price = self._build_price(flt)
        alerts = self._build_alerts(flt, now=run_at)
        notifications = self._build_notifications(flt)
        runner = self._build_runner(flt)
        audit = self._build_audit(flt)
        summary = classify_dashboard_health(
            crawler=crawler,
            price=price,
            alerts=alerts,
            notifications=notifications,
            runner=runner,
            audit=audit,
        )
        logger.info(
            "dashboard.operations.viewed",
            extra={"event": "dashboard.operations.viewed", "health": summary.health.value},
        )
        return PriceBrainDashboardSnapshot(
            generated_at=run_at,
            summary=summary,
            crawler=crawler,
            price=price,
            alerts=alerts,
            notifications=notifications,
            runner=runner,
            audit=audit,
        )

    def _target_filter(self, flt: DashboardFilter) -> TargetListFilter:
        return TargetListFilter(
            mall_id=flt.mall_id,
            category=flt.category,
            tag=flt.tag,
        )

    def _alert_filter(self, flt: DashboardFilter) -> AlertListFilter:
        return AlertListFilter(
            mall_id=flt.mall_id,
            category=flt.category,
        )

    def _price_filter(self, flt: DashboardFilter) -> PriceListFilter:
        return price_filter_from_target_filter(self._target_filter(flt))

    def _build_crawler(self, flt: DashboardFilter, *, now: datetime) -> CrawlerDashboardSummary:
        try:
            target_filter = self._target_filter(flt)
            summary = self._crawler.summarize(now=now)
            targets = self._crawler.list_targets(filters=target_filter, now=now)
            failed_targets = [item for item in targets if item.is_failed]
            ssg_denied = sum(
                1 for item in failed_targets if (item.last_error_code or "") in SSG_DENIED_CODES
            )
            high_priority_failed = sum(
                1 for item in failed_targets if item.priority >= HIGH_PRIORITY_THRESHOLD
            )
            recent_failures = self._crawler.list_recent_failures(
                limit=max(flt.recent, 1),
                mall_id=flt.mall_id,
            )
            by_mall = tuple(
                (item.mall_id, item.total)
                for item in self._crawler.summarize_by_mall(now=now)
                if flt.mall_id is None or item.mall_id == flt.mall_id.strip().lower()
            )
            return CrawlerDashboardSummary(
                total_targets=(
                len(targets)
                if flt.mall_id or flt.category or flt.tag
                else summary.total_targets
            ),
                enabled_targets=sum(1 for item in targets if item.enabled),
                disabled_targets=sum(1 for item in targets if not item.enabled),
                failed_targets=len(failed_targets),
                ssg_access_denied=ssg_denied,
                high_priority_failed=high_priority_failed,
                recent_successes=max(summary.success_targets, 0),
                recent_failures=len(recent_failures),
                by_mall=by_mall,
                recent_failure_targets=tuple(item.to_dict() for item in recent_failures[: flt.recent]),
            )
        except Exception as exc:
            return CrawlerDashboardSummary(read_error=str(exc))

    def _build_price(self, flt: DashboardFilter) -> PriceDashboardSummary:
        try:
            gpu = self._price.summarize_gpu_prices(filters=self._price_filter(flt))
            return PriceDashboardSummary(
                targets=gpu.targets,
                with_price=gpu.with_price,
                without_price=gpu.without_price,
                price_down=gpu.price_down,
                price_up=gpu.price_up,
                unchanged=gpu.unchanged,
                no_history=gpu.no_history,
                invalid_price=gpu.invalid_price,
            )
        except Exception as exc:
            return PriceDashboardSummary(read_error=str(exc))

    def _build_alerts(self, flt: DashboardFilter, *, now: datetime) -> AlertDashboardSummary:
        try:
            alert_filter = self._alert_filter(flt)
            summary = self._alert.summarize_alerts(filters=alert_filter, now=now)
            invalid_events = self._audit.list_events(
                filters=AuditEventFilter(
                    event_type=AuditEventType.ALERT_INVALID.value,
                    mall_id=flt.mall_id,
                    recent=flt.recent,
                )
            )
            return AlertDashboardSummary(
                total=summary.total,
                enabled=summary.enabled,
                disabled=summary.disabled,
                triggered_recently=summary.triggered_recently,
                never_triggered=summary.never_triggered,
                invalid=summary.invalid,
                by_type=summary.by_type,
                recent_invalid=len(invalid_events),
            )
        except Exception as exc:
            return AlertDashboardSummary(read_error=str(exc))

    def _build_notifications(self, flt: DashboardFilter) -> NotificationDashboardSummary:
        try:
            summary = self._alert.summarize_notifications(recent_limit=flt.recent)
            return NotificationDashboardSummary(
                sent=summary.notification_sent,
                failed=summary.notification_failed,
                skipped=summary.notification_skipped,
                by_channel=summary.by_channel,
                recent_failures=summary.recent_failures,
            )
        except Exception as exc:
            return NotificationDashboardSummary(read_error=str(exc))

    def _build_runner(self, flt: DashboardFilter) -> RunnerDashboardSummary:
        try:
            health = self._alert.get_runner_health(recent_limit=max(flt.recent, 1))
            recent_cycles = health.recent_cycles
            failed_cycles = sum(
                1
                for item in recent_cycles
                if item.get("errors") or int(item.get("notification_failed") or 0) > 0
            )
            status = runner_cycle_status(
                last_failed_cycle_at=health.last_failed_cycle_at,
                last_successful_cycle_at=health.last_successful_cycle_at,
                errors=health.errors,
                notification_failed=health.notification_failed,
            )
            return RunnerDashboardSummary(
                last_cycle_status=status,
                last_run_at=health.last_cycle_finished_at,
                duration_seconds=health.duration_seconds,
                total_alerts=health.total_alerts,
                evaluated=health.evaluated,
                triggered=health.triggered,
                notification_sent=health.notification_sent,
                notification_failed=health.notification_failed,
                last_successful_cycle_at=health.last_successful_cycle_at,
                last_failed_cycle_at=health.last_failed_cycle_at,
                recent_cycles=len(recent_cycles),
                recent_failed_cycles=failed_cycles,
            )
        except Exception as exc:
            return RunnerDashboardSummary(read_error=str(exc))

    def _build_audit(self, flt: DashboardFilter) -> AuditDashboardSummary:
        try:
            base_filter = AuditEventFilter(
                mall_id=flt.mall_id,
                recent=flt.recent,
                failures_only=flt.failures_only,
            )
            events = self._audit.list_events(filters=base_filter)
            summary = self._audit.summarize_events(filters=base_filter)
            triggered = self._audit.list_events(
                filters=AuditEventFilter(
                    event_type=AuditEventType.ALERT_TRIGGERED.value,
                    mall_id=flt.mall_id,
                    recent=flt.recent,
                )
            )
            notification_failed = self._audit.list_events(
                filters=AuditEventFilter(
                    event_type=AuditEventType.NOTIFICATION_FAILED.value,
                    mall_id=flt.mall_id,
                    recent=flt.recent,
                )
            )
            runner_failed = self._audit.list_events(
                filters=AuditEventFilter(
                    event_type=AuditEventType.RUNNER_CYCLE_FAILED.value,
                    recent=flt.recent,
                )
            )
            failure_events = [
                item for item in events if item.event and _is_failure_event(item.event.event_type)
            ]
            return AuditDashboardSummary(
                recent_events=len(events),
                recent_failures=len(failure_events),
                recent_alert_triggered=len(triggered),
                recent_notification_failed=len(notification_failed),
                recent_runner_failed=len(runner_failed),
                event_snapshots=tuple(item.to_dict() for item in events[: flt.recent]),
                read_error=(
                    f"{summary.read_errors} malformed audit events"
                    if summary.read_errors
                    else None
                ),
            )
        except Exception as exc:
            return AuditDashboardSummary(read_error=str(exc))


def _is_failure_event(event_type: AuditEventType) -> bool:
    return event_type in {
        AuditEventType.ALERT_INVALID,
        AuditEventType.NOTIFICATION_FAILED,
        AuditEventType.RUNNER_CYCLE_FAILED,
    }
