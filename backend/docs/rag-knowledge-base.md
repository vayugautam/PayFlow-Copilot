# PayFlow Copilot RAG knowledge base

Phase 3 stores relational document metadata in PostgreSQL and document chunks,
embeddings, and retrieval payloads in Qdrant Cloud. It does not call an LLM.

## Setup

1. Copy `.env.example` to `.env`.
2. Set `QDRANT_URL`, `QDRANT_API_KEY`, and `QDRANT_COLLECTION_NAME`.
3. Set `GEMINI_API_KEY`. Phase 3 uses the official Gemini SDK with
   `gemini-embedding-001` and 768-dimensional vectors. Document chunks use
   `RETRIEVAL_DOCUMENT`; queries use `RETRIEVAL_QUERY`.
4. Run `alembic upgrade head` from `backend/`.

The Qdrant collection is created on first use with cosine distance and the
configured vector dimension. API keys are read only from environment settings
and are never persisted in either database.

## Upload and retrieval

Authenticate using the existing `/api/v1/auth/login` endpoint, then upload:

```text
POST /api/v1/knowledge/documents
Authorization: Bearer <token>
Content-Type: multipart/form-data
file=@policy.txt
```

Retrieve semantic matches:

```json
POST /api/v1/knowledge/retrieve
{"query":"How long do refunds take?", "top_k":5}
```

Every Qdrant search is filtered by the authenticated user ID and, when supplied,
the owned document ID. Document deletion removes matching Qdrant points before
deleting PostgreSQL metadata. Failed ingestion removes any partial points and
the metadata row so it can be retried; a failed cleanup leaves the relational
row in a recoverable processing state and returns an error.

PostgreSQL stores document ownership and ingestion metadata. Qdrant stores
chunk text, source metadata, and vectors. API keys are never persisted in either
store.

## Phase 4 configuration

`LLM_PROVIDER`, `LLM_MODEL`, and `LLM_API_KEY` are reserved for the next phase.
They are deliberately independent from embedding settings and are not used here.

## Retrieval evaluation and relevance threshold

`backend_data/rag_evaluation_dataset.json` contains synthetic policy questions
covering refunds, eligibility, duplicates, settlement, disputes, timelines, and
an unrelated question. `scripts/evaluate_rag.py` and
`app/services/rag_evaluation.py` calculate Hit Rate@K, Precision@K, Recall@K,
MRR, and citation correctness from explicit document/chunk labels. The evaluator
does not connect to or modify a production Qdrant collection.

`KNOWLEDGE_SIMILARITY_THRESHOLD` remains configurable and defaults to `0.0`.
No universal threshold is claimed: a production threshold must be selected only
after collecting score distributions from the target collection and validating
the resulting false-positive/false-negative tradeoff. Retrieval with no
supporting result is insufficient evidence, and citation lists remain empty.
