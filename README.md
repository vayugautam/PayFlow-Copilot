# PayFlow Copilot

PayFlow Copilot is a portfolio-scale payment operations assistant. It combines
user-scoped transaction data, deterministic payment analysis, policy retrieval,
and an AI chat experience to help support teams investigate payment issues and
prepare dispute drafts.

> This is a simulated payment-support application. It does not move money,
> issue real refunds, contact banks, or integrate with payment networks.

## Problem statement

Payment support work often requires combining transaction facts, policy
documents, and a careful explanation of what can happen next. A general-purpose
LLM can produce fluent but unsafe answers if it is allowed to infer payment
facts, invent citations, or decide dispute outcomes.

## Why PayFlow Copilot exists

The project demonstrates how to place an LLM inside a controlled backend:
authoritative transaction facts and deterministic rules stay in application
services, while the model provides conversational explanation and drafting.

## Key features

- JWT registration, login, and user-scoped access.
- Transaction listing, filtering, pagination, detail, and deterministic analysis.
- Policy document ingestion and retrieval through Gemini embeddings and Qdrant.
- Tool-calling chat with transaction analysis and policy citations.
- Structured dispute drafts with evidence classifications and explicit review.
- Dispute lifecycle, audit events, request IDs, security headers, and rate limits.
- Backend unit, contract, RAG evaluation, and PostgreSQL integration test tiers.

## Architecture diagram

<!-- mermaid-checked: no \n, no em-dash/en-dash, no {} in labels, subgraphs are id["label"], arrows are -->|"label"|, all subgraphs closed by end, ids unique -->
~~~mermaid
flowchart TD
    subgraph Client["Client"]
        Frontend["React and TypeScript"]
    end
    subgraph Backend["Backend"]
        API["FastAPI API"]
        Services["Application services"]
        Rules["Deterministic payment rules"]
    end
    subgraph Storage["Storage"]
        Postgres[("PostgreSQL")]
        Qdrant[("Qdrant Cloud")]
    end
    subgraph Providers["AI providers"]
        Gemini["Gemini embeddings"]
        Groq["Groq generation"]
    end

    Frontend -->|"HTTP and JSON"| API
    API -->|"orchestrates"| Services
    Services -->|"payment facts"| Rules
    Services -->|"relational data"| Postgres
    Services -->|"vector search"| Qdrant
    Services -->|"embed documents and queries"| Gemini
    Services -->|"bounded generation"| Groq
~~~

## Technology stack

| Area | Technology | Purpose |
|---|---|---|
| Frontend | React, TypeScript, Vite | Dashboard and protected user flows |
| Backend | FastAPI, Python | HTTP API and dependency injection |
| Relational data | PostgreSQL 16 | Users, transactions, documents, chat, disputes, audit |
| ORM | SQLAlchemy async, psycopg 3 | Async persistence |
| Migrations | Alembic | Schema versioning |
| Vector store | Qdrant Cloud | Embedded document chunks and similarity search |
| Embeddings | Gemini `gemini-embedding-001`, 768 dimensions | Retrieval vectors |
| Generation | Groq `openai/gpt-oss-120b` | Conversational explanation and draft generation |
| Testing | pytest, Vitest, Playwright | Backend and frontend verification |

## System components

- **React frontend:** authentication, dashboard, transactions, Copilot,
  disputes, and read-only audit views.
- **FastAPI routes:** authenticated API boundaries grouped by domain.
- **Application services:** ownership-scoped persistence, RAG ingestion and
  retrieval, assistant orchestration, payment analysis, and dispute lifecycle.
- **PostgreSQL:** source of truth for relational records and ownership.
- **Qdrant:** vector representation of document chunks; metadata includes
  document and user identifiers.
- **AI providers:** Gemini is used for embeddings and Groq for generation.

## Data flow

1. The browser sends a JWT-authenticated request to FastAPI.
2. The API resolves the user and applies ownership filters.
3. Domain services read PostgreSQL and, for policy questions, retrieve Qdrant
   chunks using the authenticated user ID.
4. Tool results are returned to the assistant orchestration layer.
5. Sensitive payment analysis is rendered from validated deterministic results.
6. Conversation, tool metadata, citations, and dispute evidence are persisted.

## RAG architecture

<!-- mermaid-checked: no \n, no em-dash/en-dash, no {} in labels, subgraphs are id["label"], arrows are -->|"label"|, all subgraphs closed by end, ids unique -->
~~~mermaid
flowchart LR
    Upload["Policy upload"] --> Extract["Text extraction"]
    Extract --> Chunk["Chunking"]
    Chunk --> Embed["Gemini embeddings"]
    Embed --> Store[("Qdrant chunks")]
    Query["User policy question"] --> QueryEmbed["Query embedding"]
    QueryEmbed --> Store
    Store --> Retrieve["User filtered retrieval"]
    Retrieve --> Cite["Citations and grounded context"]
~~~

Retrieval is filtered by authenticated user and optional owned document ID.
PostgreSQL document metadata must be ready before chunks are returned. The
evaluation harness measures Hit Rate@K, Precision@K, Recall@K, MRR, and citation
correctness without modifying a production collection.

## AI tool-calling architecture

<!-- mermaid-checked: no \n, no em-dash/en-dash, no {} in labels, subgraphs are id["label"], arrows are -->|"label"|, all subgraphs closed by end, ids unique -->
~~~mermaid
flowchart LR
    User["User message"] --> LLM["Groq model"]
    LLM --> Tool["Validated tool call"]
    Tool --> Backend["Authorized backend service"]
    Backend --> Result["Authoritative result"]
    Result --> LLM
    LLM --> Response["Assistant response"]
    Result --> Facts["Deterministic payment facts"]
    Facts --> Response
~~~

The model cannot execute payments, refunds, retries, status changes, or dispute
confirmation. Transaction analysis is rendered from backend results rather
than trusting free-form model claims.

## Database design

<!-- mermaid-checked: no \n, no em-dash/en-dash, no {} in labels, subgraphs are id["label"], arrows are -->|"label"|, all subgraphs closed by end, ids unique -->
~~~mermaid
flowchart TD
    Users[("users")] --> Transactions[("transactions")]
    Users --> Documents[("knowledge_documents")]
    Users --> Conversations[("conversations")]
    Conversations --> Messages[("messages")]
    Users --> Disputes[("disputes")]
    Transactions --> Disputes
    Conversations --> Disputes
    Users --> Audit[("audit_logs")]
~~~

Users own transactions, knowledge documents, conversations, and disputes.
Messages belong to conversations. Disputes reference transactions and
optionally conversations. Audit events identify the actor and affected entity.
Important indexes cover ownership plus recency, transaction lookup, document
ownership, conversation ordering, message ordering, and audit filtering. Active
disputes have a PostgreSQL partial unique index on transaction and reason.

## API overview

All paths below are under `/api/v1` except `/` and `/health`.

### Authentication

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register` | Create an account |
| POST | `/auth/login` | Issue a bearer access token |
| GET | `/auth/me` | Return the authenticated user |

Example login response:

```json
{"access_token":"<redacted>","token_type":"bearer"}
```

### Transactions

| Method | Path | Purpose |
|---|---|---|
| POST | `/transactions` | Create a transaction record |
| GET | `/transactions` | List, filter, and paginate transactions |
| GET | `/transactions/:transaction_id` | Read an owned transaction |
| GET | `/transactions/:transaction_id/analysis` | Read deterministic analysis |

### Knowledge documents

| Method | Path | Purpose |
|---|---|---|
| POST | `/knowledge/documents` | Upload a PDF or TXT policy |
| GET | `/knowledge/documents` | List owned documents |
| GET | `/knowledge/documents/:document_id` | Read document metadata |
| DELETE | `/knowledge/documents/:document_id` | Delete an owned document |
| POST | `/knowledge/retrieve` | Retrieve policy chunks |

Example retrieval request:

```json
{"query":"How long do refunds take?","top_k":5}
```

### Chat

| Method | Path | Purpose |
|---|---|---|
| POST | `/chat/conversations` | Create a conversation |
| GET | `/chat/conversations` | List conversations |
| GET | `/chat/conversations/:conversation_id` | Read a conversation |
| GET | `/chat/conversations/:conversation_id/messages` | Read messages |
| POST | `/chat/conversations/:conversation_id/messages` | Send a message |

### Disputes

| Method | Path | Purpose |
|---|---|---|
| POST | `/disputes/drafts` | Generate a reviewable draft |
| GET | `/disputes` | List owned disputes |
| GET | `/disputes/:dispute_id` | Read a dispute |
| PATCH | `/disputes/:dispute_id` | Edit a draft |
| POST | `/disputes/:dispute_id/confirm` | Explicitly mark a draft submitted internally |
| POST | `/disputes/:dispute_id/cancel` | Cancel a draft or submitted record |

### Audit logs

| Method | Path | Purpose |
|---|---|---|
| GET | `/audit-logs` | Read actor-scoped, paginated audit events |

### Payments

| Method | Path | Purpose |
|---|---|---|
| POST | `/payments/create-order` | Create an authenticated Razorpay order |
| POST | `/payments/verify-payment` | Verify the Razorpay payment signature and record the successful transaction |
| POST | `/payments/webhook` | Verify and process Razorpay payment events |
| POST | `/payments/reconcile-failure` | Reconcile a browser-reported failure with Razorpay's API |

The browser receives only `VITE_RAZORPAY_KEY_ID`. The Razorpay secret remains
in the backend environment. Configure Razorpay's webhook URL as
`https://<backend-host>/api/v1/payments/webhook`, subscribe to
`payment.failed`, `payment.authorized`, and `payment.captured`, and set the
webhook signing secret as `RAZORPAY_WEBHOOK_SECRET`. Deliveries are
signature-verified, deduplicated, and stored before processing. The
integration uses test-mode checkout and does not execute refunds.

## Security design

- Passwords are hashed with Argon2id and never returned.
- JWTs require subject, issued-at, and expiry claims.
- Transactions, documents, conversations, disputes, and audit reads are
  ownership-scoped.
- Qdrant searches include `user_id` metadata filters.
- Request IDs and safe security headers support diagnosis and browser safety.
- Login, registration, chat, and document ingestion have configurable local
  rate limits.
- Production settings reject weak secrets, wildcard CORS, localhost databases,
  and excessive token lifetimes.

## Safety boundaries

Deterministic payment rules remain authoritative for status, failure reason, and
retry eligibility. RAG citations come from retrieved chunks only. Dispute drafts
include evidence classifications and always require user review. The system
does not store raw card numbers or CVVs, move money, issue real refunds, settle
transactions, or contact a bank or payment network.

## Local setup

Prerequisites: Python 3.12, Node.js, npm, and PostgreSQL or Docker.

```text
cd backend
copy .env.example .env
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

In another terminal:

```text
cd frontend
npm install
copy .env.example .env
npm run dev
```

## Docker setup

The repository includes PostgreSQL only; it does not containerize the API or
frontend:

```text
docker compose up -d postgres
```

Then run the backend and frontend commands above. Qdrant Cloud and AI provider
credentials remain external configuration.

## Environment configuration

Copy [backend/.env.example](backend/.env.example) to `backend/.env`. Configure
the database, `SECRET_KEY`, CORS origins, rate limits, Qdrant settings, and
provider keys as needed. For Razorpay checkout, set `RAZORPAY_KEY_ID` and
`RAZORPAY_KEY_SECRET` in `backend/.env`, and set only the public key ID as
`VITE_RAZORPAY_KEY_ID` in `frontend/.env`. `backend/.env` and `frontend/.env`
are ignored and must never be committed.
The frontend optionally uses `VITE_API_BASE_URL`; local Vite development
defaults to the same-origin `/api/v1` proxy.

## Running tests

Backend unit and contract tests:

```text
cd backend
.\.venv\Scripts\python.exe -m pytest -m "not integration and not external"
```

PostgreSQL integration tests require an explicit isolated
`TEST_DATABASE_URL` and run real Alembic migrations:

```text
set TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/payflow_copilot_test
.\.venv\Scripts\python.exe -m pytest -m integration
```

Frontend:

```text
cd frontend
npm test
npm run build
npm run lint
npm run test:e2e
```

## Screenshots

No application screenshots are committed yet. See
[docs/screenshots.md](docs/screenshots.md) for the checklist and clearly
labelled placeholders. Screenshots should be captured from the running
application using non-sensitive demo data.

## Known limitations

- The local rate limiter is process-local and needs shared storage for
  horizontal scaling.
- JWT revocation and HttpOnly-cookie authentication are not implemented.
- Settlement and refund evidence are represented only by available application
  data; no bank settlement system is integrated.
- Live Groq, Gemini, and Qdrant verification requires configured services.
- PostgreSQL integration tests skip when `TEST_DATABASE_URL` is unavailable.
- Audit immutability is application-level; database-level immutability is not
  claimed.

## Future improvements

- Add shared rate-limit storage and centralized log aggregation.
- Add secure refresh-token or HttpOnly-cookie session design.
- Add provider health checks, retry telemetry, and background ingestion jobs.
- Add measured retrieval threshold calibration from production-like datasets.
- Add browser screenshots and a deployed demo environment with synthetic data.

## Engineering highlights

This project demonstrates bounded LLM tool use, deterministic payment
reasoning, ownership-aware retrieval, structured dispute evidence, async
PostgreSQL access, migration-backed integration testing, safe error handling,
request correlation, and explicit documentation of operational trade-offs.
