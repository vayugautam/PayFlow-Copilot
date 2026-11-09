# Architecture decisions

## FastAPI for the API boundary

**Context:** The application needs typed HTTP contracts, dependency injection,
async handlers, and clear route grouping.

**Decision:** Use FastAPI with Pydantic schemas and dependency-based
authentication/database access.

**Alternatives:** Django REST Framework or a synchronous Flask service.

**Trade-offs:** FastAPI provides concise typed contracts and async support, but
the team must understand async database lifecycle and external-client
boundaries.

## Asynchronous SQLAlchemy with PostgreSQL

**Context:** Transactions, conversations, disputes, and documents are
relational, ownership-sensitive records.

**Decision:** Use PostgreSQL with SQLAlchemy's async engine and psycopg 3,
versioned by Alembic.

**Alternatives:** SQLite for local persistence or a synchronous ORM.

**Trade-offs:** PostgreSQL supplies UUID, JSONB, foreign-key, partial-index,
and concurrency behavior needed by the domain. It adds a database prerequisite
for faithful integration tests.

## Qdrant for vector retrieval

**Context:** Policy chunks need semantic retrieval while document metadata and
ownership remain relational.

**Decision:** Store embeddings and chunk payloads in Qdrant Cloud, with
PostgreSQL as the metadata and ownership source of truth.

**Alternatives:** pgvector or an in-memory vector index.

**Trade-offs:** Qdrant is a specialized vector service and preserves a clear
boundary, but it introduces another operational dependency and requires
metadata filters on every search.

## Gemini embeddings

**Context:** Ingestion and query vectors must use the same embedding model and
dimensions.

**Decision:** Use Gemini `gemini-embedding-001` with 768 dimensions, using
document and query retrieval task types.

**Alternatives:** Local sentence-transformers or another hosted provider.

**Trade-offs:** Hosted embeddings simplify model operations but require API
availability and credentials.

## Groq generation

**Context:** The assistant needs bounded natural-language explanation and
structured dispute drafting.

**Decision:** Use Groq with `openai/gpt-oss-120b` behind a small adapter with
bounded retries and timeout handling.

**Alternatives:** Direct provider calls from routes or a locally hosted model.

**Trade-offs:** The adapter centralizes error handling, but generation remains
an external dependency and must not be treated as authoritative payment logic.

## Deterministic payment rules separate from generation

**Context:** Failure codes, status, and retry eligibility are safety-sensitive.

**Decision:** Analyze transactions in `payment_intelligence.py` and render
verified results separately from free-form LLM output.

**Alternatives:** Rely on a longer system prompt or ask the model to infer
failure meanings.

**Trade-offs:** Responses are safer and testable, while explanations have less
creative flexibility for sensitive payment facts.

## Explicit dispute confirmation

**Context:** A generated draft must not silently become a submitted dispute.

**Decision:** Draft creation stores `DRAFT`; only an explicit confirmation
endpoint transitions it to internally recorded `SUBMITTED`.

**Alternatives:** Automatically submit after generation.

**Trade-offs:** The workflow requires an additional user action, but it makes
review and consent observable and testable.

## Audit logs separate from conversation history

**Context:** Conversation messages explain assistant interaction, while audit
events record important business mutations.

**Decision:** Store audit events in a separate actor-scoped table and write them
alongside dispute mutations.

**Alternatives:** Infer audit history from chat messages or database logs alone.

**Trade-offs:** The application has explicit event records and filters, but
application-level append-only behavior is not database-level immutability.
