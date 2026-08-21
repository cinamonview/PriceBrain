# PriceBrain Remediation Plan

Structured, human-review remediation plans derived from Investigation findings.

## Flow

```text
Dashboard
    ↓
Investigation Operations
    ↓
Remediation Rule Engine (pure)
    ↓
RemediationPlan
    ↓
Operator review / approval
```

This layer is **plan-only**. It does not execute crawler retries, change alerts, dispatch notifications, or write to Firestore.

## Finding → Action mapping

| Finding code | Action type | Priority | Risk |
|--------------|-------------|----------|------|
| `CRAWLER_ACCESS_DENIED` | `REVIEW_SSG_ACCESS` | HIGH | HIGH |
| `CRAWLER_HTTP_ERROR` | `REVIEW_CRAWLER_TARGET` | HIGH | HIGH |
| `CRAWLER_NO_SUCCESS` | `REVIEW_CRAWLER_TARGET` | HIGH | MEDIUM |
| `PRICE_NO_HISTORY` | `REVIEW_PRICE_HISTORY` | MEDIUM | MEDIUM |
| `PRICE_READ_ERROR` | `REVIEW_PRICE_HISTORY` | HIGH | HIGH |
| `ALERT_NO_RECENT_EVALUATION` | `REVIEW_ALERT` | MEDIUM | MEDIUM |
| `ALERT_READ_ERROR` | `REVIEW_ALERT` | HIGH | HIGH |
| `NOTIFICATION_FAILURE` | `REVIEW_NOTIFICATION` | HIGH | HIGH |
| `NOTIFICATION_FAILURE_REPEATED` | `REVIEW_NOTIFICATION` | CRITICAL | HIGH |
| `RUNNER_CYCLE_FAILED` | `REVIEW_RUNNER` | HIGH | MEDIUM |
| `RUNNER_CYCLE_FAILURE_REPEATED` | `REVIEW_RUNNER` | CRITICAL | HIGH |
| `AUDIT_READ_ERROR` | `REVIEW_AUDIT` | MEDIUM | MEDIUM |
| `RUNNER_HEALTHY` | `NO_ACTION` | LOW | LOW |
| unknown code | `VERIFY_CONFIGURATION` | MEDIUM | MEDIUM |

Rules live in `remediation_rules.py` and are independent from `investigation_rules.py`.

## Priority and risk

- **Priority** — urgency of operator attention
- **Risk** — potential operational impact if ignored

Actions are sorted by:

```text
priority DESC → risk DESC → occurred_at DESC → action_id ASC
```

## Human approval boundary

Every `RemediationAction` defaults to:

```text
human_approval_required = true
auto_executable = false
```

This step intentionally stops at:

```text
Investigation → Remediation Plan → human review
```

No automatic remediation is performed in this phase.

## Why no auto-execution yet

PriceBrain operational write paths (crawler, alerts, notifications, runner) have strict responsibility boundaries. Automatic actions could:

- mutate Firestore state unintentionally
- re-trigger alerts or notifications
- mask environment-specific SSG constraints

A future **Action Executor** layer can consume approved `RemediationAction` objects without changing this plan schema.

## CLI

```bash
python -m pricebrain_app.scripts.show_pricebrain_remediation
python -m pricebrain_app.scripts.show_pricebrain_remediation --json
python -m pricebrain_app.scripts.show_pricebrain_remediation --failures --json
python -m pricebrain_app.scripts.show_pricebrain_remediation --priority high --json
python -m pricebrain_app.scripts.show_pricebrain_remediation --area crawler --json
python -m pricebrain_app.scripts.show_pricebrain_remediation --target-id ssg_1000832367906 --json
```

## Security / read-only

Remediation plan generation must not:

- write to Firestore
- perform HTTP requests
- run crawler / scheduler / worker / runner
- dispatch notifications
- trigger alerts

JSON output uses `collect_secrets_for_redaction()`.

## Failure isolation

- malformed findings → isolated `read_error` on that action
- unknown finding codes → `VERIFY_CONFIGURATION` fallback
- dashboard section read errors do not abort the entire plan

## Future Action Executor

Possible future extension:

```text
RemediationPlan
    ↓
Human approval record
    ↓
ActionExecutor (separate phase)
    ↓
Controlled operational change
```

The current DTOs include `action_type`, `preconditions`, and `metadata` to support that extension without redesign.
