"""Build notification events from price alert evaluation results."""

from __future__ import annotations

import uuid
from datetime import datetime

from pricebrain_app.crawler.notification_models import NotificationChannel, NotificationEvent
from pricebrain_app.crawler.price_alert_models import AlertEvaluationOutcome, AlertEvaluationResult, PriceAlert
from pricebrain_app.crawler.price_calculations import calculate_price_change, calculate_price_change_percent
from pricebrain_app.crawler.price_ops_models import PriceSnapshot
from pricebrain_app.crawler.targets import utc_now


def build_notification_event(
    alert: PriceAlert,
    result: AlertEvaluationResult,
    snapshot: PriceSnapshot,
    *,
    channel: NotificationChannel,
    now: datetime | None = None,
) -> NotificationEvent | None:
    if result.outcome is not AlertEvaluationOutcome.TRIGGERED:
        return None

    run_at = now or utc_now()
    current = result.current_price
    previous = result.previous_price
    price_change = calculate_price_change(current, previous)
    price_change_percent = calculate_price_change_percent(current, previous)

    title = f"Price alert triggered: {alert.alert_type.value}"
    message = result.message or "price alert condition satisfied"

    return NotificationEvent(
        notification_id=uuid.uuid4().hex,
        alert_id=alert.alert_id,
        target_id=alert.target_id,
        mall_id=alert.mall_id,
        alert_type=alert.alert_type.value,
        channel=channel,
        title=title,
        message=message,
        current_price=current,
        previous_price=previous,
        price_change=price_change,
        price_change_percent=price_change_percent,
        product_name=snapshot.product_name or alert.product_name,
        brand=alert.brand,
        created_at=run_at,
        metadata={"threshold": alert.threshold},
    )
