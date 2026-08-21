# Notification Adapters

PriceBrain notifications extend the price alert layer without changing crawler, worker, pipeline, or repository write paths.

## Architecture

```text
PriceAlertService
      ↓
AlertEvaluationResult (TRIGGERED)
      ↓
NotificationEvent
      ↓
NotificationDispatcher
      ↓
NotificationAdapter
      ├── ConsoleNotificationAdapter
      └── FakeNotificationAdapter
```

Future adapters (not implemented yet):

```text
Email / SMS / Discord / Slack / Telegram
```

## Responsibilities

| Layer | Responsibility |
|-------|----------------|
| `PriceAlertService` | Decide trigger, update `price_alerts`, optionally dispatch notifications |
| `notification_builder` | Build `NotificationEvent` from alert evaluation |
| `NotificationDispatcher` | Select adapter by channel |
| `NotificationAdapter` | Deliver event to a channel |

Notification failures are isolated from alert evaluation. A failed notification does not mark the alert evaluation as failed.

## NotificationEvent

Key fields:

- `notification_id`, `alert_id`, `target_id`, `mall_id`
- `alert_type`, `channel`, `title`, `message`
- `current_price`, `previous_price`, `price_change`, `price_change_percent`
- `product_name`, `brand`, `metadata`, `created_at`

Missing price values are allowed and handled safely.

## NotificationAdapter Interface

```python
class NotificationAdapter(ABC):
    channel: NotificationChannel

    def send(self, event: NotificationEvent) -> NotificationSendResult:
        ...
```

Built-in adapters in this phase:

- `ConsoleNotificationAdapter` — structured log output only
- `FakeNotificationAdapter` — in-memory test adapter, no network

## Dispatcher

`NotificationDispatcher.dispatch(event)`:

1. Logs `notification.created`
2. Finds adapter for `event.channel`
3. Calls `adapter.send(event)`
4. Returns `NotificationSendResult`

Unsupported channels return `UNSUPPORTED`. Adapter exceptions return `FAILED`.

## Configuration

Environment variables (see `.env.example`):

```text
PRICEBRAIN_NOTIFICATION_ENABLED=false
PRICEBRAIN_NOTIFICATION_DEFAULT_CHANNEL=console
```

No webhook URLs, SMTP passwords, or API keys are stored in the repository.

## CLI

Smoke test without external services:

```bash
python -m pricebrain_app.scripts.test_notifications
python -m pricebrain_app.scripts.test_notifications --json
```

Price alert check optionally includes notification results when notifications are enabled:

```bash
python -m pricebrain_app.scripts.check_price_alerts --json
```

## Observability Events

- `notification.created`
- `notification.dispatched`
- `notification.sent`
- `notification.failed`
- `notification.skipped`
- `notification.unsupported`

Logs never include API keys, Bearer tokens, Authorization headers, webhook secrets, or Firebase credentials.

## Security

Do not commit:

- `.env`
- `secrets/`
- `local/`
- credentials or real operational URLs

Example URLs in docs use `https://example.com/...` placeholders only.

## Future Extensions

### External adapters

Implement `NotificationAdapter` for each channel:

```text
pricebrain_app/crawler/adapters/notifications/
```

Register adapters in `build_default_dispatcher()` or a dedicated factory.

Do not add external HTTP calls in this repository until a dedicated adapter phase is approved.

### Notification history

This phase does not persist notification delivery history.

Future optional collection:

```text
notifications/{notification_id}
```

Keep delivery history separate from `price_alerts` trigger state.

## Current Scope

This phase intentionally does **not** connect:

- SMTP / SendGrid
- Twilio
- Discord / Slack / Telegram webhooks
- Firebase Cloud Messaging

All delivery verification uses Console and Fake adapters only.
