# PayFlow Copilot security threat model

## Scope and assets

Assets include user credentials, JWTs, transaction metadata, private knowledge
documents and chunks, dispute drafts, audit records, provider credentials, and
request correlation data. PayFlow Copilot uses simulated payment transactions;
it does not execute real payments, refunds, settlements, or bank operations.

## Trust boundaries and threats

- The browser and user input are untrusted clients.
- FastAPI authentication and ownership queries separate users from relational
  and Qdrant data. Cross-user access, IDOR, and private-document leakage remain
  primary threats.
- Retrieved documents and prompts are untrusted content and may contain prompt
  injection or poisoned policy claims.
- LLM output may hallucinate transaction, refund, settlement, dispute, or policy
  facts. Tools must remain authorized and server-side.
- Login, registration, chat, ingestion, and dispute endpoints can be abused for
  brute force, cost exhaustion, or denial of service.
- Dispute confirmation is a sensitive state transition and must remain explicit.
- Audit records are actor-scoped and application append-only; database-level
  immutability is not claimed.
- Secrets, passwords, JWTs, CVVs, and raw card data must not enter logs or audit
  metadata.

## Mitigations

- JWTs require `sub`, `iat`, and `exp`; expired, malformed, invalid, and inactive
  sessions return a generic 401 response.
- Passwords use Argon2id and schema validation enforces minimum length.
- Ownership predicates scope transactions, documents, conversations, disputes,
  and audit reads to the authenticated user.
- Qdrant searches include `user_id` and optional owned `document_id` filters.
- Deterministic transaction analysis and structured dispute evidence validation
  prevent unsupported sensitive claims and fabricated citations.
- Request IDs, duration/status logging, redaction rules, safe exception
  responses, and security headers improve operational diagnosis.
- Configurable in-memory rate limits protect authentication and expensive
  operations. This limiter is per-process and is not sufficient for a
  horizontally scaled deployment; shared storage is required there.
- Production settings reject weak JWT configuration, localhost databases,
  wildcard CORS, excessive token lifetimes, and invalid rate limits.

## Residual risks

The local limiter can be bypassed across processes or instances. JWT revocation
is not implemented. HSTS is enabled only in production and assumes HTTPS is
terminated correctly. Provider, database, and Qdrant availability remain
operational dependencies. This threat model is not a security guarantee or a
production-compliance certification.
