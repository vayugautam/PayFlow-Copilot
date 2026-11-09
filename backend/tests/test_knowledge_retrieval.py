from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models import User
from app.services import knowledge_service


class FakeDb:
    def __init__(self, documents):
        self.documents = documents

    async def scalars(self, _statement):
        return iter(self.documents)


class FakeQdrant:
    def __init__(self, hits):
        self.hits = hits
        self.requested_user_id = None

    async def search(self, vector, user_id, top_k, document_id=None):
        self.requested_user_id = user_id
        return self.hits[:top_k]


@pytest.mark.asyncio
async def test_retrieve_preserves_scores_metadata_and_ownership_filter(monkeypatch):
    user_id = uuid4()
    user = User(id=user_id)
    document_id = uuid4()
    private_document_id = uuid4()
    document = SimpleNamespace(
        id=document_id,
        title="Refund policy",
        filename="refund.txt",
        status="ready",
    )
    qdrant = FakeQdrant(
        [
            SimpleNamespace(
                score=0.91,
                payload={
                    "document_id": str(document_id),
                    "user_id": str(user_id),
                    "chunk_id": f"{document_id}:0",
                    "chunk_index": 0,
                    "page_number": 1,
                    "content": "Refunds are reviewed within five days.",
                },
            ),
            SimpleNamespace(
                score=0.99,
                payload={
                    "document_id": str(private_document_id),
                    "user_id": str(uuid4()),
                    "chunk_index": 0,
                    "content": "Private document",
                },
            ),
        ]
    )
    monkeypatch.setattr(knowledge_service, "embed_texts", _embed_texts)

    results = await knowledge_service.retrieve(
        FakeDb([document]), user, "refund timing", 5, qdrant=qdrant
    )

    assert qdrant.requested_user_id == user_id
    assert len(results) == 1
    assert results[0]["document_id"] == document_id
    assert results[0]["chunk_id"] == f"{document_id}:0"
    assert results[0]["score"] == 0.91


@pytest.mark.asyncio
async def test_retrieve_excludes_deleted_or_missing_documents(monkeypatch):
    user = User(id=uuid4())
    missing_id = uuid4()
    qdrant = FakeQdrant(
        [
            SimpleNamespace(
                score=0.8,
                payload={
                    "document_id": str(missing_id),
                    "chunk_index": 0,
                    "content": "Deleted content",
                },
            )
        ]
    )
    monkeypatch.setattr(knowledge_service, "embed_texts", _embed_texts)

    results = await knowledge_service.retrieve(
        FakeDb([]), user, "deleted policy", 5, qdrant=qdrant
    )

    assert results == []


async def _embed_texts(texts, task_type):
    return [[0.1] for _ in texts]
