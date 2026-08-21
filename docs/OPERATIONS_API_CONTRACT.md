# Operations API Contract

Stable HTTP contract for read-only operations endpoints.

## Endpoints

| Method | Path | Response Model |
|--------|------|----------------|
| GET | `/api/operations/dashboard` | `DashboardResponse` |
| GET | `/api/operations/investigation` | `InvestigationResponse` |
| GET | `/api/operations/remediation` | `RemediationPlanResponse` |
| GET | `/api/operations/execution` | `ExecutionResponse` |
| GET | `/api/operations/command-center` | `CommandCenterResponse` |

All endpoints require `Authorization: Bearer <Firebase ID Token>`.

## Error Contract

| Status | Meaning |
|--------|---------|
| 401 | Missing, invalid, malformed, or expired token |
| 403 | Authenticated but missing OPS role |
| 500 | Unexpected internal error |

Error body:

```json
{"detail": "..."}
```

Never included in errors:

- ID token / Authorization header
- API keys / credentials / secrets
- stack traces / file paths

## Role Contract

| Role | Access |
|------|--------|
| OPS_VIEWER | All 5 GET endpoints |
| OPS_OPERATOR | All 5 GET endpoints |
| OPS_ADMIN | All 5 GET endpoints |

No role / unknown role → 403.

No HTTP mutation endpoints exist in this contract.

## Remediation Plan Contract

`GET /api/operations/remediation` returns plan metadata only.

Every actionable item maintains:

- `human_approval_required=true`
- `auto_executable=false`

No execute endpoint is exposed.

## OpenAPI

- `BearerAuth` security scheme
- Response schemas exposed per endpoint
- 401 / 403 / 500 documented
- GET-only under `/api/operations/*`

## Validation Flow

```text
Operations View → dict → redact_payload() → Pydantic schema → JSON response
```

Malformed view payloads return 500 without leaking validation internals.

## Future Extension

Web Dashboard will consume this contract in a later phase. Contract stability is prioritized over frontend implementation in this gate.
