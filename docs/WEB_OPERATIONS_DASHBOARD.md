# PriceBrain Web Operations Dashboard

Read-only web dashboard for PriceBrain Operations API.

## Stack

- React + TypeScript
- Vite
- Firebase Authentication (ID token)
- React Router

## Setup

```bash
cd web
cp .env.example .env.local
npm install
npm run dev
```

Development server:

- Frontend: http://127.0.0.1:5173
- API proxy: `/api/*` → `http://127.0.0.1:8000`

Backend must be running separately:

```bash
uvicorn pricebrain_app.main:app --reload
```

## Authentication

The web app uses Firebase Authentication and sends:

```http
Authorization: Bearer <Firebase ID Token>
```

Custom claims:

- `ops_roles` or `roles`
- `OPS_VIEWER`, `OPS_OPERATOR`, `OPS_ADMIN`

Tokens are managed by Firebase SDK session persistence. The UI does not render tokens.

## Scope (current phase)

Implemented:

- Login / logout
- Dashboard shell
- Command Center
- Dashboard cards
- API client
- Auto refresh (read-only)
- Remediation plan-only policy banner

Placeholder only:

- Investigation detail
- Execution history detail
- Audit detail

Not implemented:

- Remediation execute
- Approval token UI
- Any mutation actions

## Security

- No secrets in source code
- Use `web/.env.local` for Firebase config
- Do not commit `.env.local`

## Tests

```bash
cd web
npm test
```
