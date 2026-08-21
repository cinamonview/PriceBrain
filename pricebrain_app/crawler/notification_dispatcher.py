"""Notification dispatcher — route events to registered adapters."""

from __future__ import annotations

import logging
from typing import Iterable

from pricebrain_app.config.settings import Settings, get_settings
from pricebrain_app.crawler.logging_utils import get_crawler_logger
from pricebrain_app.crawler.notification_adapter import (
    ConsoleNotificationAdapter,
    FakeNotificationAdapter,
    NotificationAdapter,
)
from pricebrain_app.crawler.notification_events import log_notification_event
from pricebrain_app.crawler.notification_models import (
    NotificationChannel,
    NotificationEvent,
    NotificationSendResult,
    NotificationSendStatus,
    parse_notification_channel,
)

logger = get_crawler_logger("crawler.notification")


class NotificationDispatcher:
    """Select adapter by channel and dispatch notification events."""

    def __init__(self, adapters: dict[NotificationChannel, NotificationAdapter] | None = None) -> None:
        self._adapters: dict[NotificationChannel, NotificationAdapter] = dict(adapters or {})

    def register(self, channel: NotificationChannel, adapter: NotificationAdapter) -> None:
        self._adapters[channel] = adapter

    def dispatch(self, event: NotificationEvent) -> NotificationSendResult:
        log_notification_event(
            logger,
            "notification.created",
            notification_id=event.notification_id,
            alert_id=event.alert_id,
            target_id=event.target_id,
            mall_id=event.mall_id,
            channel=event.channel.value,
            message=event.title,
        )

        adapter = self._adapters.get(event.channel)
        if adapter is None:
            result = NotificationSendResult(
                status=NotificationSendStatus.UNSUPPORTED,
                channel=event.channel,
                notification_id=event.notification_id,
                message=f"no adapter registered for channel {event.channel.value}",
            )
            log_notification_event(
                logger,
                "notification.unsupported",
                notification_id=event.notification_id,
                alert_id=event.alert_id,
                target_id=event.target_id,
                channel=event.channel.value,
                status=result.status.value,
                message=result.message,
            )
            return result

        log_notification_event(
            logger,
            "notification.dispatched",
            notification_id=event.notification_id,
            alert_id=event.alert_id,
            target_id=event.target_id,
            channel=event.channel.value,
        )

        try:
            result = adapter.send(event)
        except Exception as exc:
            result = NotificationSendResult(
                status=NotificationSendStatus.FAILED,
                channel=event.channel,
                notification_id=event.notification_id,
                message=str(exc),
            )
            log_notification_event(
                logger,
                "notification.failed",
                notification_id=event.notification_id,
                alert_id=event.alert_id,
                target_id=event.target_id,
                channel=event.channel.value,
                status=result.status.value,
                message=result.message,
            )
            return result

        event_name = _event_for_status(result.status)
        log_notification_event(
            logger,
            event_name,
            notification_id=event.notification_id,
            alert_id=event.alert_id,
            target_id=event.target_id,
            channel=event.channel.value,
            status=result.status.value,
            message=result.message,
        )
        return result


def build_default_dispatcher(
    *,
    settings: Settings | None = None,
    extra_adapters: Iterable[NotificationAdapter] | None = None,
) -> NotificationDispatcher:
    resolved = settings or get_settings()
    dispatcher = NotificationDispatcher()
    dispatcher.register(NotificationChannel.CONSOLE, ConsoleNotificationAdapter())
    dispatcher.register(NotificationChannel.FAKE, FakeNotificationAdapter())
    if extra_adapters:
        for adapter in extra_adapters:
            dispatcher.register(adapter.channel, adapter)
    return dispatcher


def resolve_default_channel(settings: Settings | None = None) -> NotificationChannel:
    resolved = settings or get_settings()
    return parse_notification_channel(resolved.pricebrain_notification_default_channel)


def notifications_enabled(settings: Settings | None = None) -> bool:
    resolved = settings or get_settings()
    return bool(resolved.pricebrain_notification_enabled)


def _event_for_status(status: NotificationSendStatus) -> str:
    if status is NotificationSendStatus.SENT:
        return "notification.sent"
    if status is NotificationSendStatus.SKIPPED:
        return "notification.skipped"
    if status is NotificationSendStatus.UNSUPPORTED:
        return "notification.unsupported"
    return "notification.failed"
