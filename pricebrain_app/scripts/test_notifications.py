"""Smoke-test the notification adapter pipeline without external services."""

from __future__ import annotations

import argparse
import sys

from pricebrain_app.crawler.notification_adapter import FakeNotificationAdapter
from pricebrain_app.crawler.notification_dispatcher import NotificationDispatcher
from pricebrain_app.crawler.notification_models import NotificationChannel, NotificationEvent, NotificationSendStatus
from pricebrain_app.crawler.ops_cli import collect_secrets_for_redaction, print_json
from pricebrain_app.crawler.targets import utc_now


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Test notification adapter pipeline.")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    fake = FakeNotificationAdapter()
    dispatcher = NotificationDispatcher({NotificationChannel.FAKE: fake})
    event = NotificationEvent(
        notification_id="test-notification-001",
        alert_id="alert-test-001",
        target_id="ssg_1000832367906",
        mall_id="ssg",
        alert_type="PRICE_BELOW",
        channel=NotificationChannel.FAKE,
        title="Test notification",
        message="Notification pipeline smoke test",
        current_price=1_490_000,
        previous_price=1_599_000,
        price_change=-109_000,
        price_change_percent=-6.82,
        product_name="Test GPU",
        brand="test-brand",
        created_at=utc_now(),
    )
    result = dispatcher.dispatch(event)

    payload = {
        "event": event.to_dict(),
        "result": result.to_dict(),
        "fake_sent_count": len(fake.sent_events),
    }

    if args.json:
        print_json(payload, secrets=collect_secrets_for_redaction())
        return 0

    print(
        "\n".join(
            [
                "Notification Pipeline Test",
                "",
                f"status: {result.status.value}",
                f"channel: {result.channel.value}",
                f"notification_id: {result.notification_id}",
                f"fake_sent_count: {len(fake.sent_events)}",
            ]
        )
    )
    return 0 if result.status is NotificationSendStatus.SENT else 1


if __name__ == "__main__":
    raise SystemExit(main())
