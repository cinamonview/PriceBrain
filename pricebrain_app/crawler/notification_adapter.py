"""Notification adapter interface and built-in adapters."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from pricebrain_app.crawler.logging_utils import get_crawler_logger
from pricebrain_app.crawler.notification_models import (
    NotificationChannel,
    NotificationEvent,
    NotificationSendResult,
    NotificationSendStatus,
)

logger = get_crawler_logger("crawler.notification")


class NotificationAdapter(ABC):
    """Send a notification event to a specific channel."""

    channel: NotificationChannel

    @abstractmethod
    def send(self, event: NotificationEvent) -> NotificationSendResult:
        raise NotImplementedError


class ConsoleNotificationAdapter(NotificationAdapter):
    channel = NotificationChannel.CONSOLE

    def __init__(self, output_logger: logging.Logger | None = None) -> None:
        self._logger = output_logger or logger

    def send(self, event: NotificationEvent) -> NotificationSendResult:
        self._logger.info(
            "notification console output",
            extra={
                "event": "notification.sent",
                "notification_id": event.notification_id,
                "alert_id": event.alert_id,
                "target_id": event.target_id,
                "channel": event.channel.value,
                "title": event.title,
                "message": event.message,
            },
        )
        return NotificationSendResult(
            status=NotificationSendStatus.SENT,
            channel=self.channel,
            notification_id=event.notification_id,
            message="delivered to console adapter",
        )


class FakeNotificationAdapter(NotificationAdapter):
    """In-memory adapter for tests — no external network calls."""

    channel = NotificationChannel.FAKE

    def __init__(self) -> None:
        self.sent_events: list[NotificationEvent] = []
        self.should_fail: bool = False
        self.failure_message: str = "fake adapter failure"

    def send(self, event: NotificationEvent) -> NotificationSendResult:
        if self.should_fail:
            raise RuntimeError(self.failure_message)
        self.sent_events.append(event)
        return NotificationSendResult(
            status=NotificationSendStatus.SENT,
            channel=self.channel,
            notification_id=event.notification_id,
            message="delivered to fake adapter",
        )


class FailingNotificationAdapter(NotificationAdapter):
    """Adapter that always raises — used to test failure isolation."""

    channel = NotificationChannel.FAKE

    def send(self, event: NotificationEvent) -> NotificationSendResult:
        raise RuntimeError("simulated adapter failure")
