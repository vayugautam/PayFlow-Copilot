# Interview guide

## 60-second introduction

PayFlow Copilot is a simulated payment-support platform built with React,
FastAPI, PostgreSQL, Qdrant, Gemini embeddings, and Groq generation. Its main
engineering goal is to make an LLM useful without letting it invent payment
facts. Transactions are analyzed deterministically, policy answers cite
user-owned retrieved chunks, and dispute drafts require explicit review and
confirmation. I also added request correlation, safe errors, rate limits,
Alembic migrations, and a PostgreSQL integration-test tier.

## Two-minute technical explanation

The React frontend calls authenticated FastAPI routes. FastAPI dependencies
resolve the JWT user and every domain service applies ownership predicates.
PostgreSQL stores users, transactions, document metadata, conversations,
messages, disputes, and audit events. Policy files are extracted and chunked,
embedded with Gemini, and stored in Qdrant with user and document metadata.

For chat, the model can request bounded tools. The backend validates tool
arguments, executes authorized services, and feeds structured results back to
the model. Payment analysis is not delegated to the model: a deterministic
service classifies status and supported failure codes. Dispute generation uses
Pydantic validation and rejects citations that were not retrieved.

## Architecture walkthrough

Explain the system as four boundaries: browser, API and application services,
relational/vector storage, and external AI providers. PostgreSQL is the source
of truth for ownership and business records; Qdrant is a retrieval index, not
the ownership authority.

## RAG explanation

Documents are extracted, normalized, chunked, embedded, and upserted into
Qdrant. Retrieval always carries the authenticated user ID and can constrain to
an owned document. Results retain scores, document IDs, chunk IDs, pages, and
source metadata. Citations are generated only from retrieved results. The
evaluation harness reports measured metrics; it does not claim a threshold or
quality improvement without data.

## Tool-calling explanation

The LLM can request `get_transaction`, `list_transactions`,
`analyze_transaction_failure`, or `retrieve_payment_policy`. Pydantic validates
arguments, the service layer enforces ownership, and tool results are recorded.
The model cannot issue payments, refunds, retries, status changes, or dispute
confirmation.

## Database design explanation

Users own the main business records. Transactions support deterministic
analysis. Knowledge documents hold relational metadata while chunks live in
Qdrant. Conversations contain ordered messages. Disputes reference transactions
and optionally conversations. Audit events are actor-scoped and written with
important dispute changes.

## Security discussion

Passwords use Argon2id. JWTs require subject, issued-at, and expiry claims.
Authentication failures are generic, ownership filters are applied in services,
and Qdrant filters include user metadata. Request IDs and security headers help
operations. The current rate limiter is process-local, so a scaled deployment
needs shared storage.

## Error handling and observability

Requests receive a correlation ID and logs record method, route, status, and
duration without bodies or secrets. Database and unexpected failures return
safe messages while diagnostic details remain server-side. External AI clients
use bounded retries and timeouts.

## Testing strategy

Unit and contract tests use isolated doubles. RAG evaluation uses deterministic
labels. PostgreSQL integration tests require an explicit isolated
`TEST_DATABASE_URL`, run Alembic migrations, and skip clearly when unavailable.
External provider tests are separate and mocked for ordinary backend tests.

## Difficult trade-offs

- A deterministic answer is safer than a completely free-form answer for
  payment facts, but less flexible.
- Qdrant keeps vector search specialized, but adds an operational dependency.
- Explicit dispute confirmation adds friction but prevents accidental state
  transitions.
- Process-local rate limiting is easy to run locally but does not scale across
  instances.

## Known limitations

There is no real payment processor, bank settlement feed, refund execution,
JWT revocation, or horizontally shared limiter. PostgreSQL integration tests
need a separately configured database. The application is a portfolio project,
not a production-compliance claim.

## Potential interviewer questions

### Why not let the LLM interpret a failure code?

Because payment-code semantics vary and an incorrect retry recommendation can
harm users. The deterministic service owns the mapping and returns unknown when
evidence is insufficient.

### Why keep PostgreSQL and Qdrant?

They solve different problems. PostgreSQL provides relational integrity and
ownership; Qdrant provides vector similarity. The boundary is explicit and
Qdrant payload filters prevent cross-user retrieval.

### What happens if policy retrieval returns nothing?

The system treats it as insufficient evidence and does not fabricate a citation
or claim policy support.

### Can a generated dispute be submitted automatically?

No. Draft creation and explicit confirmation are separate operations. The
confirmation endpoint records an internal submitted state and audit events; it
does not contact an external processor.

### How would you scale the system?

Move rate-limit state to shared storage, add centralized structured logs and
metrics, isolate ingestion jobs, add provider health telemetry, and provision
separate PostgreSQL and Qdrant environments.

### What would you test with a real database?

Migration head, PostgreSQL constraints and indexes, ownership persistence,
transaction filtering, conversation ordering, dispute lifecycle, and audit
events. Groq, Gemini, and Qdrant remain mocked unless a separate external
smoke test is intentionally run.
