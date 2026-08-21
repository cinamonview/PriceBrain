"""Price alert runner — orchestrates alert evaluation and notification dispatch."""

from __future__ import annotations

import signal
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from pricebrain_app.config.settings import Settings, get_settings
from pricebrain_app.crawler.logging_utils import get_crawler_logger
from pricebrain_app.crawler.alert_ops_health_store import record_alert_ops_cycle
from pricebrain_app.crawler.notification_models import NotificationSendStatus
from pricebrain_app.crawler.price_alert_runner_events import log_price_alert_runner_event
from pricebrain_app.crawler.price_alert_service import AlertCheckSummary, PriceAlertService
from pricebrain_app.crawler.targets import utc_now

logger = get_crawler_logger("crawler.price_alert_runner")


@dataclass(frozen=True)
class PriceAlertRunnerConfig:
    interval_seconds: float = 60.0


@dataclass(frozen=True)
class PriceAlertRunnerCycleResult:
    cycle_started_at: datetime
    cycle_finished_at: datetime
    total_alerts: int
    evaluated: int
    triggered: int
    skipped: int
    invalid: int
    not_triggered: int
    notification_sent: int
    notification_failed: int
    errors: tuple[str, ...] = ()
    dry_run: bool = False
    shutdown_requested: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_started_at": self.cycle_started_at.isoformat(),
            "cycle_finished_at": self.cycle_finished_at.isoformat(),
            "total_alerts": self.total_alerts,
            "evaluated": self.evaluated,
            "triggered": self.triggered,
            "skipped": self.skipped,
            "invalid": self.invalid,
            "not_triggered": self.not_triggered,
            "notification_sent": self.notification_sent,
            "notification_failed": self.notification_failed,
            "errors": list(self.errors),
            "dry_run": self.dry_run,
            "shutdown_requested": self.shutdown_requested,
        }


@dataclass
class AlertRunnerShutdown:
    """Cooperative shutdown for the price alert runner."""

    _stop: bool = field(default=False, init=False)

    @property
    def should_stop(self) -> bool:
        return self._stop

    def request_stop(self) -> None:
        if not self._stop:
            log_price_alert_runner_event(logger, "price_alert_runner.shutdown_requested")
        self._stop = True

    def register(self) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, self._handle_signal)
            except (AttributeError, ValueError, OSError):
                continue

    def _handle_signal(self, _signum: int, _frame: object) -> None:
        self.request_stop()


class PriceAlertRunner:
    """Operational runner for enabled price alerts."""

    def __init__(
        self,
        service: PriceAlertService,
        *,
        config: PriceAlertRunnerConfig | None = None,
        shutdown: AlertRunnerShutdown | None = None,
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        self._service = service
        self._config = config or _config_from_settings()
        self._shutdown = shutdown or AlertRunnerShutdown()
        self._sleep_func = sleep_func

    def run_once(
        self,
        *,
        dry_run: bool = False,
        max_alerts: int | None = None,
        dispatch_notifications: bool | None = None,
        now: datetime | None = None,
    ) -> PriceAlertRunnerCycleResult:
        started_at = now or utc_now()
        log_price_alert_runner_event(
            logger,
            "price_alert_runner.started",
            dry_run=dry_run,
        )
        errors: list[str] = []
        try:
            results, summary, notifications = self._service.check_enabled_alerts(
                now=started_at,
                dispatch_notifications=dispatch_notifications,
                dry_run=dry_run,
                max_alerts=max_alerts,
            )
        except Exception as exc:
            finished_at = utc_now()
            message = str(exc)
            errors.append(message)
            log_price_alert_runner_event(
                logger,
                "price_alert_runner.alert_failed",
                message=message,
            )
            failed_cycle = PriceAlertRunnerCycleResult(
                cycle_started_at=started_at,
                cycle_finished_at=finished_at,
                total_alerts=0,
                evaluated=0,
                triggered=0,
                skipped=0,
                invalid=0,
                not_triggered=0,
                notification_sent=0,
                notification_failed=0,
                errors=tuple(errors),
                dry_run=dry_run,
                shutdown_requested=self._shutdown.should_stop,
            )
            record_alert_ops_cycle(failed_cycle)
            return failed_cycle

        notification_sent = sum(
            1 for item in notifications if item.status is NotificationSendStatus.SENT
        )
        notification_failed = sum(
            1 for item in notifications if item.status is NotificationSendStatus.FAILED
        )
        for item in notifications:
            if item.status is NotificationSendStatus.FAILED:
                log_price_alert_runner_event(
                    logger,
                    "price_alert_runner.notification_failed",
                    message=item.message,
                )

        if summary.failed:
            errors.append(f"{summary.failed} alert evaluation failures")

        finished_at = utc_now()
        cycle = PriceAlertRunnerCycleResult(
            cycle_started_at=started_at,
            cycle_finished_at=finished_at,
            total_alerts=summary.total,
            evaluated=len(results) + summary.failed,
            triggered=summary.triggered,
            skipped=summary.skipped,
            invalid=summary.invalid,
            not_triggered=summary.not_triggered,
            notification_sent=notification_sent,
            notification_failed=notification_failed,
            errors=tuple(errors),
            dry_run=dry_run,
            shutdown_requested=self._shutdown.should_stop,
        )
        log_price_alert_runner_event(
            logger,
            "price_alert_runner.completed",
            total_alerts=cycle.total_alerts,
            triggered=cycle.triggered,
            invalid=cycle.invalid,
            notification_failed=cycle.notification_failed,
            dry_run=dry_run,
        )
        record_alert_ops_cycle(cycle, results=results, notifications=notifications)
        return cycle

    def run_forever(
        self,
        *,
        dry_run: bool = False,
        max_alerts: int | None = None,
        dispatch_notifications: bool | None = None,
        interval_seconds: float | None = None,
    ) -> PriceAlertRunnerCycleResult:
        interval = interval_seconds if interval_seconds is not None else self._config.interval_seconds
        self._shutdown.register()
        last_result = _empty_cycle_result()
        try:
            while not self._shutdown.should_stop:
                last_result = self.run_once(
                    dry_run=dry_run,
                    max_alerts=max_alerts,
                    dispatch_notifications=dispatch_notifications,
                )
                if self._shutdown.should_stop:
                    break
                if interval > 0:
                    self._sleep_func(interval)
        finally:
            log_price_alert_runner_event(logger, "price_alert_runner.stopped")
        return last_result

    def shutdown(self) -> None:
        self._shutdown.request_stop()


def _config_from_settings(settings: Settings | None = None) -> PriceAlertRunnerConfig:
    resolved = settings or get_settings()
    return PriceAlertRunnerConfig(interval_seconds=resolved.pricebrain_alert_runner_interval_seconds)


def _empty_cycle_result() -> PriceAlertRunnerCycleResult:
    now = utc_now()
    return PriceAlertRunnerCycleResult(
        cycle_started_at=now,
        cycle_finished_at=now,
        total_alerts=0,
        evaluated=0,
        triggered=0,
        skipped=0,
        invalid=0,
        not_triggered=0,
        notification_sent=0,
        notification_failed=0,
    )
