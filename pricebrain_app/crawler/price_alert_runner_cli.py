"""Shared CLI helpers for price alert runner commands."""

from __future__ import annotations

from pricebrain_app.config.settings import get_settings
from pricebrain_app.crawler.notification_dispatcher import build_default_dispatcher
from pricebrain_app.crawler.price_alert_cli import build_price_alert_repository
from pricebrain_app.crawler.price_alert_runner import PriceAlertRunner, PriceAlertRunnerConfig
from pricebrain_app.crawler.price_alert_service import PriceAlertService
from pricebrain_app.crawler.price_ops_cli import build_price_operations_view


def build_price_alert_runner(
    *,
    interval_seconds: float | None = None,
) -> PriceAlertRunner:
    settings = get_settings()
    service = PriceAlertService(
        build_price_alert_repository(),
        build_price_operations_view(),
        notification_dispatcher=build_default_dispatcher(),
    )
    config = PriceAlertRunnerConfig(
        interval_seconds=(
            interval_seconds
            if interval_seconds is not None
            else settings.pricebrain_alert_runner_interval_seconds
        )
    )
    return PriceAlertRunner(service, config=config)
