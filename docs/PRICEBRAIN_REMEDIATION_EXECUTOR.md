# PriceBrain Remediation Executor

Human-approved execution boundary for remediation plans.

## Flow

```text
Dashboard
    ↓
Investigation
    ↓
RemediationPlan
    ↓
Human Review
    ↓
Action Executor (PLAN / DRY_RUN / EXECUTE)
    ↓
Read-only Handler verification
```

## Execution modes

| Mode | Behavior | Mutation |
|------|----------|----------|
| `PLAN` | Describe intended action | None |
| `DRY_RUN` | Invoke read-only handler verification | None |
| `EXECUTE` | Requires approval token + handler invocation | None in this phase |

Default CLI behavior is **PLAN ONLY**.

## Human approval boundary

`EXECUTE` requires:

1. `--execute` flag
2. `--action-id`
3. `--approval-token`
4. Token bound to the same `action_id`
5. `human_approval_required=true` on the action

Tokens are:

- verified via in-memory digest store (test/dev phase)
- never logged
- never included in JSON output
- never stored in audit metadata
- never written to Firestore in plaintext

## Action handlers

Handlers live in `remediation_action_handlers.py`.

Current handlers are **read-only verification handlers**:

- read crawler target status
- read price history
- read alert snapshot
- read notification/runner/audit summaries

They do **not** mutate Firestore or call external HTTP APIs.

## Why handlers are read-only now

This phase validates:

- approval boundary
- execution mode separation
- failure isolation
- audit integration
- security gates

Future mutation capabilities (target enable/disable, alert edits, notification retry) require:

- dedicated mutation handler
- dedicated approval policy
- dedicated gate tests
- explicit operator runbook

## Audit events

Executor results map to audit events:

- `REMEDIATION_PLANNED`
- `REMEDIATION_APPROVAL_BLOCKED`
- `REMEDIATION_DRY_RUN`
- `REMEDIATION_EXECUTED`
- `REMEDIATION_FAILED`

Approval tokens are excluded from audit metadata.

## Failure isolation

- malformed action → `BLOCKED` for that action only
- handler exception → `FAILED` for that action only
- approval failure → `BLOCKED`, other actions continue in `execute_plan()`
- missing handler → `BLOCKED`

## Security model

- secret redaction via `collect_secrets_for_redaction()`
- no hardcoded production tokens
- no `.env` / `secrets/` / `local/` dependencies for approval
- `EXECUTE ≠ unrestricted mutation`

## CLI

```bash
python -m pricebrain_app.scripts.execute_pricebrain_remediation
python -m pricebrain_app.scripts.execute_pricebrain_remediation --preview --json
python -m pricebrain_app.scripts.execute_pricebrain_remediation --dry-run --json
python -m pricebrain_app.scripts.execute_pricebrain_remediation \
  --execute --action-id <id> --approval-token <token> --json
```

## Future Action Executor extension

The executor interface is designed for a future phase:

```text
Approved RemediationAction
    ↓
Mutation Handler (separate gate)
    ↓
Controlled operational change
    ↓
Audit + rollback plan
```

Keep mutation handlers separate from read-only verification handlers.
