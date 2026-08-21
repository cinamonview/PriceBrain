# PriceBrain Operations API

Read-only HTTP API for operations visibility.

## Architecture

```text
FastAPI
   ↓
Operations API (/api/operations/*)
   ↓
CommandCenterOperationsView
   ├── DashboardOperationsView
   ├── InvestigationOperationsView
   ├── RemediationOperationsView
   └── ExecutionOperationsView
   ↓
existing repositories / in-memory stores
```

The API performs query and serialization only. No operational actions are executed.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/operations/dashboard` | Dashboard snapshot |
| GET | `/api/operations/investigation` | Investigation findings |
| GET | `/api/operations/remediation` | Remediation plan (plan only) |
| GET | `/api/operations/execution` | Execution history |
| GET | `/api/operations/command-center` | Full command center snapshot |

All endpoints are read-only. They do not execute crawler, runner, notification, alert, or remediation actions.

## Query Parameters

### Dashboard

- `category` (default: gpu)
- `mall`
- `tag`
- `recent` (default: 10)
- `failures`

### Investigation

- `area`, `target_id`, `alert_id`, `failures`, `recent`
- dashboard filters: `category`, `mall`, `tag`

### Remediation

- `priority`, `area`, `target_id`, `failures`, `recent`
- dashboard filters: `category`, `mall`, `tag`

No execute endpoint exists.

### Execution

- `status`, `target_id`, `alert_id`, `action_id`, `failures`, `blocked`, `recent`

### Command Center

- `category`, `mall`, `tag`, `recent`, `failures`, `blocked`

## Response Policy

Operational states such as `DEGRADED`, `CRITICAL`, `UNKNOWN`, `SSG_ACCESS_DENIED`, and `NO_HISTORY` are returned as normal `200 OK` JSON responses.

## Security

Responses are redacted using `collect_secrets_for_redaction()` before return.

Never included:

- API keys
- credentials
- bearer tokens
- approval tokens
- webhook secrets
- `.env` values

## Failure Isolation

Section read errors (for example `crawler.read_error`) do not fail the entire API response when underlying views isolate failures.

## Explicitly Forbidden Endpoints

Not implemented in this phase:

- `POST /remediation/execute`
- `POST /alerts/trigger`
- `POST /notifications/send`
- `POST /runner/start`
- `POST /crawler/run`

## CLI Parity

Existing CLI commands remain the primary operator interface. API exposes the same read-only view data over HTTP.
