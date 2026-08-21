# Operations API Authentication & Authorization

Read-only operations API access control using Firebase ID tokens.

## Architecture

```text
Client
  ↓
Authorization: Bearer <Firebase ID Token>
  ↓
FastAPI dependency (get_current_user)
  ↓
Token verifier (Firebase or fake emulator)
  ↓
AuthenticatedUser
  ↓
Authorization (require_ops_viewer)
  ↓
Operations API endpoint
  ↓
Existing read-only Operations Views
```

Authentication and authorization are kept outside Operations Views.

## Firebase ID Token Verification

Production path:

```text
FirebaseTokenVerifier
  ↓
firebase_admin.auth.verify_id_token()
  ↓
AuthenticatedUser(uid, email, roles, claims)
```

Roles are read from custom claims:

- `ops_roles`
- `roles`

## Role Model

| Role | Current Access |
|------|----------------|
| `OPS_VIEWER` | Read all operations endpoints |
| `OPS_OPERATOR` | Same read-only access (future execute extension point) |
| `OPS_ADMIN` | Same read-only access (no HTTP mutation in this phase) |

All roles are read-only in this phase. No HTTP mutation endpoints exist.

## HTTP Status Policy

| Case | Status |
|------|--------|
| Missing token | `401 Authentication required` |
| Invalid / malformed / expired token | `401 Invalid authentication token` |
| Valid token, insufficient role | `403 Insufficient permissions` |
| Valid token + allowed role | `200 OK` |

Error messages never include the raw token value.

## Environment Variables

```text
PRICEBRAIN_AUTH_ENABLED=true
PRICEBRAIN_AUTH_EMULATOR=false
```

- `PRICEBRAIN_AUTH_ENABLED=false` — local bypass with synthetic viewer user (development only)
- `PRICEBRAIN_AUTH_EMULATOR=true` — use in-memory `FakeTokenVerifier` instead of Firebase network verification

Placeholders only in `.env.example`. No real Firebase credentials in repository.

## Test Environment

pytest uses:

```text
FakeTokenVerifier + FastAPI dependency override
```

No Firebase network calls during tests.

Test tokens (non-JWT placeholders):

- `test-ops-viewer-token`
- `test-ops-operator-token`
- `test-ops-admin-token`

## Secret Handling

Never stored or returned:

- ID token
- refresh token
- access token
- Authorization header
- Firebase private keys

Responses pass through existing `collect_secrets_for_redaction()`.

## Read-only Boundary

Authentication protects read access only. It does not add:

- remediation execute
- alert trigger
- notification dispatch
- runner start
- crawler run

Forbidden methods on `/api/operations/*`:

- POST / PUT / PATCH / DELETE

## Future Mutation Authorization

`OPS_OPERATOR` and `OPS_ADMIN` roles are separated for future gated mutation endpoints. Those endpoints will require separate approval boundaries and are not part of this phase.
