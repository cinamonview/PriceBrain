# PriceBrain Operations Dashboard

Read-only aggregation layer that combines existing crawler, price, alert, notification, runner, and audit operations views into a single operator-facing snapshot.

## Purpose

Operators can answer operational questions without opening Firestore Console or tailing logs:

- Crawler target health and failures
- GPU price observation status
- Price alert status and recent triggers
- Notification delivery outcomes
- Price alert runner cycle health
- Recent audit events and failures

The dashboard is **read-only**. It never crawls, writes to Firestore, triggers alerts, dispatches notifications, or runs the alert runner.

## Architecture

```text
CrawlerOperationsView
PriceOperationsView
AlertOperationsView
AuditOperationsView
        ↓
DashboardOperationsView.build_dashboard_snapshot()
        ↓
PriceBrainDashboardSnapshot
```

Existing calculation logic is reused. The dashboard does not duplicate repository or evaluation policies.

## Dashboard sections

| Section | Source | Key fields |
|---------|--------|------------|
| Crawler | `CrawlerOperationsView` | targets, enabled/disabled, failed, `SSG_ACCESS_DENIED`, mall breakdown |
| Price | `PriceOperationsView.summarize_gpu_prices()` | with/without price, up/down/unchanged, no history |
| Alerts | `AlertOperationsView.summarize_alerts()` | total, enabled, triggered recently, never triggered |
| Notifications | `AlertOperationsView.summarize_notifications()` | sent/failed/skipped, channel breakdown |
| Runner | `AlertOperationsView.get_runner_health()` | last cycle status, duration, recent cycles |
| Audit | `AuditOperationsView` | recent events, failures, triggered/failed counts |

## Health classification

Pure function: `classify_dashboard_health()` in `dashboard_health.py`.

| Status | Meaning |
|--------|---------|
| `HEALTHY` | Main sections loaded; no recent severe operational failures |
| `DEGRADED` | Partial failures, notification failures, invalid alerts, audit read errors, single runner cycle failure, crawler target failures including `SSG_ACCESS_DENIED` |
| `CRITICAL` | Most dashboard sections failed to load, or repeated runner cycle failures |
| `UNKNOWN` | Insufficient data to classify |

Important: **`SSG_ACCESS_DENIED` alone does not produce `CRITICAL`.** HTTP 403 against SSG is a known environment constraint. The dashboard surfaces it explicitly under crawler metrics but treats it as degraded operations visibility, not total system failure.

## CLI usage

Human-readable dashboard:

```bash
python -m pricebrain_app.scripts.show_pricebrain_dashboard
```

JSON output:

```bash
python -m pricebrain_app.scripts.show_pricebrain_dashboard --json
```

Recent audit-oriented slice:

```bash
python -m pricebrain_app.scripts.show_pricebrain_dashboard --recent 10 --json
```

Failure-focused audit slice:

```bash
python -m pricebrain_app.scripts.show_pricebrain_dashboard --failures --json
```

GPU-only filter:

```bash
python -m pricebrain_app.scripts.show_pricebrain_dashboard --category gpu --json
```

Mall filter:

```bash
python -m pricebrain_app.scripts.show_pricebrain_dashboard --mall ssg --json
```

## JSON structure

```json
{
  "generated_at": "...",
  "summary": {
    "health": "HEALTHY",
    "reasons": []
  },
  "crawler": {},
  "price": {},
  "alerts": {},
  "notifications": {},
  "runner": {},
  "audit": {}
}
```

Secret masking reuses `collect_secrets_for_redaction()`.

## Read-only guarantee

Dashboard snapshot generation must not:

- write to Firestore
- perform HTTP requests
- execute crawler/worker/scheduler code paths
- call `mark_triggered()`
- dispatch notifications
- run `PriceAlertRunner.run_once()`

## Failure isolation

Each dashboard section is built independently. If one section fails, others continue loading and the failing section records `read_error`.

Examples:

- malformed audit event → audit `read_error`, other sections unaffected
- price summary failure → price `read_error`, crawler/alerts still shown

## SSG 403 interpretation

When crawler targets show:

```text
last_status=HTTP_ERROR
last_error_code=SSG_ACCESS_DENIED
```

the dashboard counts them under `crawler.ssg_access_denied`. Price observation may be suppressed for those targets when no history exists. This is expected in current environments and should not be interpreted as PriceBrain core service outage.

## Future Web UI

The dashboard DTO (`PriceBrainDashboardSnapshot`) is designed for a future read-only Web UI or monitoring endpoint. A web layer can call `build_dashboard_snapshot()` and render the same JSON/text structure without changing operational write paths.
