# PayFlow Copilot Frontend

Phase 6A/6B provides a React + TypeScript + Vite fintech dashboard with JWT authentication,
AI Copilot conversations, transaction search/detail views, and deterministic payment analysis.

## Setup

```text
npm install
copy .env.example .env
npm run dev
```

Set `VITE_API_BASE_URL` to the backend API root, normally
`http://127.0.0.1:8000/api/v1`. The backend must be running separately:

```text
cd ..\backend
uvicorn app.main:app --reload
```

## Commands

```text
npm run build
npm run test
npm run lint
```

## Authentication

Login calls `/auth/login`, validates the returned bearer token through `/auth/me`, and stores
only the access token in `sessionStorage` for the current browser tab. Passwords are never
stored. This is a deliberate tradeoff for the existing bearer-JWT backend: session storage
reduces persistence compared with local storage but is still readable by JavaScript. The
backend does not currently provide HttpOnly-cookie authentication, so the frontend does not
claim that protection.

## Implemented

- `/login` and `/register`
- Protected routes and logout
- Responsive application shell with navigation
- `/dashboard` with real transaction/dispute endpoints
- `/copilot` with conversation history, grounded assistant messages, citations, and tool status
- `/transactions` with server-side search, status filtering, pagination, and detail views
- Transaction failure analysis from the deterministic backend endpoint
- `/disputes` with draft creation, review, editing, explicit confirmation, cancellation, and lifecycle states
- `/audit-logs` with reverse-chronological activity, supported filters, pagination, and read-only details
- Loading, empty, retry, and API error states

Settings remains a later-phase placeholder. Dispute confirmation is an explicit user action
and records submission internally in PayFlow Copilot only; it does not contact a bank, card
network, or external processor. Audit logs are displayed read-only because the backend
exposes no edit or delete operations. The
Copilot never fabricates responses: conversations, messages, citations, and tool metadata
come from the backend API. The transaction detail action opens Copilot with a supported
message draft containing the selected transaction ID; it does not add an undocumented
backend request field.
