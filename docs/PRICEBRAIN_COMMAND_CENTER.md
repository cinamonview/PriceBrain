# PriceBrain Operations Command Center

Read-only operations stack from dashboard through execution history.

## Stack

```text
Dashboard
  ↓
Investigation
  ↓
RemediationPlan
  ↓
Human Review
  ↓
RemediationExecutor
  ↓
ExecutionResult
  ↓
Execution History
  ↓
Operations Command Center
```

## Audit Event vs Execution History

| Concern | Audit Event | Execution History |
|---------|-------------|-------------------|
| Question | What event occurred? | What remediation action produced what result? |
| Store | `AuditEventStore` | `ExecutionHistoryStore` |
| Scope | Alerts, notifications, runner cycles, remediation audit | PLAN / DRY_RUN / EXECUTE outcomes |
| Persistence | In-memory bounded deque | In-memory bounded deque |
| Firestore | No new collection | No new collection |

Remediation executor writes both:

- Audit event (event-oriented, existing types)
- Execution history entry (action-oriented, operator trace)

They are complementary, not duplicates. Audit does not replace execution history and vice versa.

## Execution History

`ExecutionHistoryStore` records:

- execution_id, action_id, action_type
- mode (PLAN / DRY_RUN / EXECUTE)
- status (PLANNED / DRY_RUN / EXECUTED / BLOCKED / FAILED / SKIPPED)
- priority, risk, area, target_id, alert_id
- timing and outcome metadata

Never stored:

- approval_token
- API keys
- Authorization headers
- credentials
- webhook URLs

## Execution Health

Pure function `classify_execution_health()`:

- `HEALTHY`: no recent failures or blocks
- `DEGRADED`: one BLOCKED / FAILED / approval failure
- `CRITICAL`: repeated failures or approval boundary issues
- `UNKNOWN`: no history

This is execution-specific health. Dashboard health classification is unchanged.

## Command Center

`CommandCenterOperationsView` composes existing views:

- Dashboard
- Investigation
- Remediation plan
- Execution history

No new crawler, Firestore, or HTTP calls are added.

## Human Approval

Approval boundary remains in `remediation_approval.py` and `remediation_executor.py`.

Execution history records approval outcomes (`approval_verified`, `error_code`) but never the token.

## Security

- `collect_secrets_for_redaction()` on all CLI JSON output
- metadata sanitization on record
- read-only handlers only (no operational mutation)

## Failure Isolation

- malformed history entry → record error counter, system continues
- malformed audit parse → execution queries continue
- one action failure does not stop plan execution or history recording

## CLI

```bash
python -m pricebrain_app.scripts.show_pricebrain_command_center
python -m pricebrain_app.scripts.show_pricebrain_command_center --json
python -m pricebrain_app.scripts.show_pricebrain_command_center --failures --json
python -m pricebrain_app.scripts.show_pricebrain_command_center --blocked --json
python -m pricebrain_app.scripts.show_pricebrain_command_center --recent 10 --json
python -m pricebrain_app.scripts.show_pricebrain_command_center --target-id ssg_1000832367906 --json
python -m pricebrain_app.scripts.show_pricebrain_command_center --action-id <action_id> --json
```

## Future Mutation Handlers

Mutation handlers require separate gates. Current execution history supports operator traceability before any mutation capability is added.
