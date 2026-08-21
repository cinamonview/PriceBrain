"""Notification models — events, channels, and send results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pricebrain_app.crawler.targets import utc_now


class NotificationChannel(str, Enum):
    CONSOLE = "CONSOLE"
    FAKE = "FAKE"
    EMAIL = "EMAIL"
    SMS = "SMS"
    DISCORD = "DISCORD"
    SLACK = "SLACK"
    TELEGRAM = "TELEGRAM"


class NotificationSendStatus(str, Enum):
    SENT = "SENT"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    UNSUPPORTED = "UNSUPPORTED"


CLI_CHANNEL_CHOICES = {
    "console": NotificationChannel.CONSOLE,
    "fake": NotificationChannel.FAKE,
}


@dataclass(frozen=True)
class NotificationEvent:
    notification_id: str
    alert_id: str
    target_id: str
    mall_id: str
    alert_type: str
    channel: NotificationChannel
    title: str
    message: str
    current_price: int | None = None
    previous_price: int | None = None
    price_change: int | None = None
    price_change_percent: float | None = None
    product_name: str | None = None
    brand: str | None = None
    created_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "alert_id": self.alert_id,
            "target_id": self.target_id,
            "mall_id": self.mall_id,
            "alert_type": self.alert_type,
            "channel": self.channel.value,
            "title": self.title,
            "message": self.message,
            "current_price": self.current_price,
            "previous_price": self.previous_price,
            "price_change": self.price_change,
            "price_change_percent": self.price_change_percent,
            "product_name": self.product_name,
            "brand": self.brand,
            "created_at": _iso(self.created_at),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class NotificationSendResult:
    status: NotificationSendStatus
    channel: NotificationChannel
    notification_id: str
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "channel": self.channel.value,
            "notification_id": self.notification_id,
            "message": self.message,
        }


def parse_notification_channel(value: str) -> NotificationChannel:
    key = value.strip().lower()
    if key in CLI_CHANNEL_CHOICES:
        return CLI_CHANNEL_CHOICES[key]
    try:
        return NotificationChannel(value.strip().upper())
    except ValueError as exc:
        supported = ", ".join(sorted(item.value for item in NotificationChannel))
        raise ValueError(f"Unsupported notification channel: {value}. Supported: {supported}") from exc


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=utc_now().tzinfo)
    return value.isoformat()
