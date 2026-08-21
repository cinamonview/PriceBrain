# Price Alerts

PriceBrain price alerts are a read-only evaluation layer on top of `PriceOperationsView`.
They do not crawl, ingest, or mutate `price_history`.

## Architecture

```text
price_history
      ↓
PriceOperationsView
      ↓
PriceAlertService
      ↓
evaluate_alert()  (pure)
      ↓
price_alerts      (Firestore)
      ↓
(future Notification Adapter)
```

Crawler, Worker, Pipeline, and Repository write paths are unchanged.

## Firestore Structure

Collection:

```text
price_alerts/{alert_id}
```

Example document:

```json
{
  "alert_id": "abc123",
  "target_id": "ssg_1000832367906",
  "mall_id": "ssg",
  "alert_type": "PRICE_BELOW",
  "threshold": 1500000,
  "enabled": true,
  "brand": "zotac",
  "product_name": "ZOTAC RTX 5080",
  "cooldown_seconds": 0,
  "last_triggered_at": null,
  "last_observed_price": null,
  "metadata": {},
  "created_at": "2026-08-21T12:00:00+00:00",
  "updated_at": "2026-08-21T12:00:00+00:00"
}
```

## Supported Alert Types

| Type | Meaning | Example threshold |
|------|---------|-------------------|
| `PRICE_BELOW` | Current price is at or below threshold | `1500000` |
| `PRICE_DROP_PERCENT` | Drop from previous price is at or above threshold percent | `20` |
| `PRICE_DROP_AMOUNT` | Drop from previous price is at or above threshold amount | `50000` |
| `PRICE_UP` | Current price is above previous price | `0` |
| `PRICE_CHANGED` | Current price differs from previous price | `0` |

Classification reuses existing price validation from `price_calculations.is_valid_price()`.

## Duplicate Prevention

Alerts store:

- `last_triggered_at`
- `last_observed_price`

Policy:

1. First evaluation that satisfies the condition → `TRIGGERED`
2. Same target, same alert, same observed price on a later run → `SKIPPED`
3. If observed price changes away and later satisfies the condition again → `TRIGGERED`

Optional `cooldown_seconds` can extend duplicate suppression for the same observed price.

## 403 / NO_HISTORY Handling

When SSG returns access denied and no valid price snapshot exists:

```text
SSG_ACCESS_DENIED
→ price = null
→ NO_HISTORY
→ alert evaluation = INVALID
```

Alerts never treat `None` as `0`.

## Invalid Price Handling

These values are not evaluated for trigger conditions:

- `None`
- `0`
- negative prices

## CLI Usage

Create a target price alert:

```bash
python -m pricebrain_app.scripts.create_price_alert \
  --target-id ssg_1000832367906 \
  --type price-below \
  --threshold 1500000
```

Percent drop alert:

```bash
python -m pricebrain_app.scripts.create_price_alert \
  --target-id ssg_1000832367906 \
  --type price-drop-percent \
  --threshold 10
```

Amount drop alert:

```bash
python -m pricebrain_app.scripts.create_price_alert \
  --target-id ssg_1000832367906 \
  --type price-drop-amount \
  --threshold 50000
```

List alerts:

```bash
python -m pricebrain_app.scripts.list_price_alerts
python -m pricebrain_app.scripts.list_price_alerts --json
```

Disable alert:

```bash
python -m pricebrain_app.scripts.disable_price_alert --alert-id <alert_id>
```

Evaluate enabled alerts:

```bash
python -m pricebrain_app.scripts.check_price_alerts
python -m pricebrain_app.scripts.check_price_alerts --json
```

`check_price_alerts` reads enabled alerts, loads the latest snapshot from `PriceOperationsView`,
evaluates conditions, and updates alert state only when triggered. It does not run crawler or ingest.

## Observability Events

Structured log events:

- `price_alert.evaluated`
- `price_alert.triggered`
- `price_alert.skipped`
- `price_alert.invalid`

Logs never include API keys, credentials, or Authorization headers.

## Future Notification Adapter

This phase stops at alert evaluation and Firestore state updates.

Future integrations (Discord, Telegram, Email) should attach after `PriceAlertService.check_enabled_alerts()`
and consume `AlertEvaluationResult` entries with outcome `TRIGGERED`.

Suggested future module:

```text
pricebrain_app/notifications/
```

Do not move alert evaluation into Worker or Crawler.

## Security

- Do not commit `.env`, `secrets/*`, or `local/gpu_targets.local.json`
- Example URLs in docs use `https://example.com/...` placeholders only
- Automated tests use `FakeFirestore` only
