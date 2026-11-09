"""Reusable Qdrant Cloud adapter with collection and access-filter helpers."""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any
from uuid import UUID, NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.core.config import get_settings


class QdrantConfigurationError(RuntimeError):
    """Raised when Qdrant is not configured or has an incompatible collection."""


class QdrantService:
    def __init__(self, client: QdrantClient | None = None):
        self.settings = get_settings()
        self.client = client

    def _client(self) -> QdrantClient:
        if self.client is None:
            if not self.settings.QDRANT_URL or not self.settings.QDRANT_API_KEY:
                raise QdrantConfigurationError("Qdrant Cloud is not configured")
            self.client = QdrantClient(
                url=self.settings.QDRANT_URL,
                api_key=self.settings.QDRANT_API_KEY,
                timeout=30,
            )
        return self.client

    async def ensure_collection(self) -> None:
        if self.settings.EMBEDDING_DIMENSION <= 0:
            raise QdrantConfigurationError("EMBEDDING_DIMENSION must be configured")

        def ensure() -> None:
            client = self._client()
            collections = client.get_collections().collections
            if not any(item.name == self.settings.QDRANT_COLLECTION_NAME for item in collections):
                client.create_collection(
                    collection_name=self.settings.QDRANT_COLLECTION_NAME,
                    vectors_config=models.VectorParams(
                        size=self.settings.EMBEDDING_DIMENSION,
                        distance=models.Distance.COSINE,
                    ),
                )
                for field in ("user_id", "document_id"):
                    client.create_payload_index(
                        collection_name=self.settings.QDRANT_COLLECTION_NAME,
                        field_name=field,
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )
                return
            info = client.get_collection(self.settings.QDRANT_COLLECTION_NAME)
            configured_size = info.config.params.vectors.size
            if configured_size != self.settings.EMBEDDING_DIMENSION:
                raise QdrantConfigurationError(
                    "Qdrant collection vector dimension does not match EMBEDDING_DIMENSION"
                )
            payload_schema = getattr(info, "payload_schema", {}) or {}
            for field in ("user_id", "document_id"):
                if field not in payload_schema:
                    client.create_payload_index(
                        collection_name=self.settings.QDRANT_COLLECTION_NAME,
                        field_name=field,
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )

        await asyncio.to_thread(ensure)

    async def upsert(self, points: list[models.PointStruct]) -> None:
        await self.ensure_collection()
        await asyncio.to_thread(
            self._client().upsert,
            collection_name=self.settings.QDRANT_COLLECTION_NAME,
            points=points,
            wait=True,
        )

    async def search(
        self,
        vector: list[float],
        user_id: UUID,
        top_k: int,
        document_id: UUID | None = None,
    ) -> list[Any]:
        await self.ensure_collection()
        conditions = [
            models.FieldCondition(key="user_id", match=models.MatchValue(value=str(user_id)))
        ]
        if document_id is not None:
            conditions.append(
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=str(document_id)),
                )
            )
        query_filter = models.Filter(must=conditions)

        def execute() -> list[Any]:
            client = self._client()
            if hasattr(client, "query_points"):
                result = client.query_points(
                    collection_name=self.settings.QDRANT_COLLECTION_NAME,
                    query=vector,
                    query_filter=query_filter,
                    limit=top_k,
                    with_payload=True,
                )
                return list(result.points)
            return list(
                client.search(
                    collection_name=self.settings.QDRANT_COLLECTION_NAME,
                    query_vector=vector,
                    query_filter=query_filter,
                    limit=top_k,
                    with_payload=True,
                )
            )

        return await asyncio.to_thread(execute)

    async def delete_document(self, document_id: UUID, user_id: UUID | None = None) -> None:
        if not self.settings.QDRANT_URL and self.client is None:
            return
        await asyncio.to_thread(
            self._client().delete,
            collection_name=self.settings.QDRANT_COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=str(document_id)),
                        ),
                        *(
                            [models.FieldCondition(
                                key="user_id",
                                match=models.MatchValue(value=str(user_id)),
                            )]
                            if user_id is not None
                            else []
                        ),
                    ]
                )
            ),
            wait=True,
        )


@lru_cache
def get_qdrant_service() -> QdrantService:
    return QdrantService()


def chunk_point_id(document_id: UUID, chunk_index: int) -> UUID:
    return uuid5(NAMESPACE_URL, f"{document_id}:{chunk_index}")
