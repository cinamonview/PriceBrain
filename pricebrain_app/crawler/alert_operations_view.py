"""Read-only alert, notification, and runner health operations queries."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from pricebrain_app.crawler.alert_operations_models import (
    AlertListFilter,
    AlertSnapshot,
    AlertSummary,
    NotificationOpsSummary,
    RunnerHealthView,
)
from pricebrain_app.crawler.alert_ops_health_store import AlertOpsHealthStore, get_alert_ops_health_store
from pricebrain_app.crawler.logging_utils import get_crawler_logger
from pricebrain_app.crawler.operations_read_cache import get_operations_read_cache
from pricebrain_app.crawler.notification_models import NotificationSendStatus
from pricebrain_app.crawler.price_alert_models import (
    PRICE_ALERTS_COLLECTION,
    PriceAlert,
    PriceAlertType,
    parse_cli_alert_type,
)
from pricebrain_app.crawler.price_alert_repository import PriceAlertRepository
from pricebrain_app.crawler.price_operations_view import PriceOperationsView
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.targets import utc_now

logger = get_crawler_logger("crawler.alert_operations")
RECENT_TRIGGER_WINDOW = timedelta(days=7)


class AlertOperationsView:
    """Read-only operations over price alerts, notifications, and runner health."""

    def __init__(
        self,
        alert_repository: PriceAlertRepository,
        target_repository: CrawlTargetRepository,
        price_operations_view: PriceOperationsView,
        *,
        health_store: AlertOpsHealthStore | None = None,
    ) -> None:
        self._alerts = alert_repository
        self._targets = target_repository
        self._prices = price_operations_view
        self._health = health_store or get_alert_ops_health_store()

    def summarize_alerts(
        self,
        *,
        filters: AlertListFilter | None = None,
        now: datetime | None = None,
    ) -> AlertSummary:
        run_at = now or utc_now()
        alerts = self._filter_alerts(filters)
        snapshots, read_errors = self._build_snapshots(alerts)
        _, malformed = self._list_alerts_safe()
        read_errors += malformed
        enabled = sum(1 for alert in alerts if alert.enabled)
        disabled = len(alerts) - enabled
        triggered_recently = sum(
            1
            for alert in alerts
            if alert.last_triggered_at is not None
            and alert.last_triggered_at >= run_at - RECENT_TRIGGER_WINDOW
        )
        never_triggered = sum(1 for alert in alerts if alert.last_triggered_at is None)
        invalid = sum(1 for item in snapshots if item.read_error is not None)
        by_type = _count_by(alerts, lambda item: item.alert_type.value)
        by_mall = _count_by(alerts, lambda item: item.mall_id)
        by_category = _count_by(
            [_category_for_alert(self._targets, alert) or "unknown" for alert in alerts],
            lambda item: item,
        )
        _log_viewed("price_alert.operations.viewed", total=len(alerts))
        return AlertSummary(
            total=len(alerts),
            enabled=enabled,
            disabled=disabled,
            triggered_recently=triggered_recently,
            never_triggered=never_triggered,
            invalid=invalid,
            by_type=by_type,
            by_mall=by_mall,
            by_category=by_category,
            read_errors=read_errors,
        )

    def list_alert_snapshots(
        self,
        *,
        filters: AlertListFilter | None = None,
    ) -> list[AlertSnapshot]:
        alerts = self._filter_alerts(filters)
        snapshots, _ = self._build_snapshots(alerts)
        _log_viewed("price_alert.operations.viewed", total=len(snapshots))
        return snapshots

    def get_alert_snapshot(self, alert_id: str) -> AlertSnapshot | None:
        alert = self._alerts.get(alert_id.strip())
        if alert is None:
            return None
        snapshot, _ = self._build_snapshot(alert)
        _log_viewed("price_alert.operations.viewed", total=1)
        return snapshot

    def summarize_notifications(
        self,
        *,
        channel: str | None = None,
        recent_limit: int = 10,
    ) -> NotificationOpsSummary:
        events = self._health.list_notifications()
        if channel is not None:
            channel_key = channel.strip().upper()
            events = [item for item in events if item.channel.upper() == channel_key]

        sent = sum(1 for item in events if item.status == NotificationSendStatus.SENT.value)
        failed = sum(1 for item in events if item.status == NotificationSendStatus.FAILED.value)
        skipped = sum(1 for item in events if item.status == NotificationSendStatus.SKIPPED.value)
        by_channel = _count_by(events, lambda item: item.channel)
        recent_events = tuple(
            item.to_dict() for item in events[: max(int(recent_limit), 0)]
        )
        recent_failures = tuple(
            item.to_dict()
            for item in events
            if item.status == NotificationSendStatus.FAILED.value
        )[: max(int(recent_limit), 0)]
        _log_viewed("notification.operations.viewed", total=len(events))
        return NotificationOpsSummary(
            total_evaluated=len(events),
            notification_sent=sent,
            notification_failed=failed,
            notification_skipped=skipped,
            by_channel=by_channel,
            recent_events=recent_events,
            recent_failures=recent_failures,
        )

    def get_runner_health(self, *, recent_limit: int = 5) -> RunnerHealthView:
        cycles = self._health.list_cycles(limit=recent_limit)
        last = cycles[0] if cycles else None
        duration = None
        if last is not None:
            duration = (last.cycle_finished_at - last.cycle_started_at).total_seconds()

        last_success = None
        last_failed = None
        for cycle in self._health.list_cycles():
            if last_failed is None and (cycle.errors or cycle.notification_failed > 0):
                last_failed = cycle.cycle_finished_at
            if last_success is None and not cycle.errors and cycle.notification_failed == 0:
                last_success = cycle.cycle_finished_at
            if last_success is not None and last_failed is not None:
                break

        _log_viewed("price_alert_runner.operations.viewed", total=len(cycles))
        return RunnerHealthView(
            last_cycle_started_at=last.cycle_started_at if last else None,
            last_cycle_finished_at=last.cycle_finished_at if last else None,
            duration_seconds=duration,
            total_alerts=last.total_alerts if last else 0,
            evaluated=last.evaluated if last else 0,
            triggered=last.triggered if last else 0,
            skipped=last.skipped if last else 0,
            invalid=last.invalid if last else 0,
            notification_sent=last.notification_sent if last else 0,
            notification_failed=last.notification_failed if last else 0,
            errors=last.errors if last else (),
            last_successful_cycle_at=last_success,
            last_failed_cycle_at=last_failed,
            recent_cycles=tuple(item.to_dict() for item in cycles),
        )

    def _filter_alerts(self, filters: AlertListFilter | None) -> list[PriceAlert]:
        flt = filters or AlertListFilter()
        alerts, _ = self._list_alerts_safe()
        if flt.target_id is not None:
            target_id = flt.target_id.strip()
            alerts = [item for item in alerts if item.target_id == target_id]
        if flt.enabled is not None:
            alerts = [item for item in alerts if item.enabled is flt.enabled]
        if flt.alert_type is not None:
            alert_type = parse_cli_alert_type(flt.alert_type.replace("_", "-"))
            alerts = [item for item in alerts if item.alert_type is alert_type]
        if flt.mall_id is not None:
            mall = flt.mall_id.strip().lower()
            alerts = [item for item in alerts if item.mall_id == mall]
        if flt.category is not None:
            category = flt.category.strip().lower()
            filtered: list[PriceAlert] = []
            for alert in alerts:
                target = self._targets.get(alert.target_id)
                target_category = (target.category or "").lower() if target else ""
                if target_category == category:
                    filtered.append(alert)
            alerts = filtered
        alerts.sort(key=lambda item: (item.target_id, item.alert_type.value, item.alert_id))
        return alerts

    def _list_alerts_safe(self) -> tuple[list[PriceAlert], int]:
        cache = get_operations_read_cache()
        if cache is not None and cache.price_alerts is not None:
            return cache.price_alerts

        alerts: list[PriceAlert] = []
        malformed = 0
        for snapshot in self._alerts._db.collection(PRICE_ALERTS_COLLECTION).stream():
            try:
                data = snapshot.to_dict() or {}
                alerts.append(PriceAlert.from_firestore_dict(data, doc_id=snapshot.id))
            except Exception:
                malformed += 1
        result = (alerts, malformed)
        if cache is not None:
            cache.price_alerts = result
        return result

    def _build_snapshots(
        self,
        alerts: list[PriceAlert],
    ) -> tuple[list[AlertSnapshot], int]:
        snapshots: list[AlertSnapshot] = []
        read_errors = 0
        for alert in alerts:
            snapshot, had_error = self._build_snapshot(alert)
            snapshots.append(snapshot)
            if had_error:
                read_errors += 1
        return snapshots, read_errors

    def _build_snapshot(self, alert: PriceAlert) -> tuple[AlertSnapshot, bool]:
        read_error = None
        current_price = None
        previous_price = None
        classification = None
        product_name = alert.product_name
        category = None
        try:
            target = self._targets.get(alert.target_id)
            if target is not None:
                category = target.category
                if not product_name:
                    product_name = target.product_name
            price = self._prices.get_current_price(alert.target_id)
            if price is not None:
                current_price = price.price
                previous_price = price.previous_price
                classification = price.classification.value
        except Exception as exc:
            read_error = str(exc)
        return (
            AlertSnapshot(
                alert_id=alert.alert_id,
                target_id=alert.target_id,
                mall_id=alert.mall_id,
                alert_type=alert.alert_type.value,
                threshold=alert.threshold,
                enabled=alert.enabled,
                current_price=current_price,
                previous_price=previous_price,
                classification=classification,
                last_observed_price=alert.last_observed_price,
                last_triggered_at=alert.last_triggered_at,
                cooldown_seconds=alert.cooldown_seconds,
                brand=alert.brand,
                product_name=product_name,
                category=category,
                read_error=read_error,
            ),
            read_error is not None,
        )


def _count_by(items: list[Any], key_fn) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for item in items:
        key = str(key_fn(item))
        counts[key] = counts.get(key, 0) + 1
    return tuple(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))


def _category_for_alert(target_repository: CrawlTargetRepository, alert: PriceAlert) -> str | None:
    target = target_repository.get(alert.target_id)
    return target.category if target is not None else None


def _log_viewed(event: str, *, total: int) -> None:
    logger.info(event, extra={"event": event, "total": total})
