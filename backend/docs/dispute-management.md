# Dispute Management and Audit Logs

Phase 5 creates user-owned dispute drafts and an append-only audit trail. Drafts use verified
transaction facts, deterministic payment analysis, and existing policy retrieval. AI output
never counts as confirmation; the user must explicitly call the confirmation endpoint.

## Structured draft evidence

Draft `evidence` includes validated `transaction_facts`, policy
`evidence_references`, `evidence_support`, `missing_information`, and
`user_review_required`. `SUPPORTED` requires at least one citation from the
retrieved policy chunks; no policy evidence is classified as
`INSUFFICIENT_EVIDENCE`. `PARTIALLY_SUPPORTED` indicates that retrieved policy
supports only part of the claim. These classifications describe evidence quality,
not the eventual dispute outcome. Transaction facts are populated by the backend,
not accepted from the model. Every draft requires user review.

## Lifecycle

`DRAFT -> SUBMITTED -> UNDER_REVIEW -> RESOLVED|REJECTED` and `DRAFT|SUBMITTED -> CANCELLED`.
`SUBMITTED` is recorded in PayFlow Copilot only. No bank, card-network, or external processor
is contacted.

## Endpoints

- `POST /api/v1/disputes/drafts`
- `GET /api/v1/disputes`
- `GET /api/v1/disputes/{dispute_id}`
- `PATCH /api/v1/disputes/{dispute_id}`
- `POST /api/v1/disputes/{dispute_id}/confirm`
- `POST /api/v1/disputes/{dispute_id}/cancel`
- `GET /api/v1/audit-logs`

All endpoints require JWT authentication and enforce ownership. Only drafts can be edited.
Repeated confirmation returns a conflict. Audit rows are appended in the same transaction as
their dispute change and never contain passwords, tokens, API keys, CVVs, or full card numbers.
There is no audit update/delete API. Audit reads are actor-scoped, newest first, filterable,
and paginated.

## Testing

From `backend/`:

```text
alembic upgrade head
pytest -q
```

Automated Groq and Qdrant calls should be mocked. Live external dispute submission is not
implemented or claimed.
