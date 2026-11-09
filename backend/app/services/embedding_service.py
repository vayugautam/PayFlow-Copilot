"""Gemini embedding generation for document indexing and retrieval."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

from app.core.config import get_settings


class EmbeddingError(RuntimeError):
    """Raised when embedding generation fails or returns invalid vectors."""


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str], *, task_type: str) -> list[list[float]]:
        raise NotImplementedError


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Adapter for the official Google Gemini SDK."""

    def __init__(self, model: str, api_key: str, dimension: int):
        self.model = model
        self.api_key = api_key
        self.dimension = dimension

    async def embed(self, texts: list[str], *, task_type: str) -> list[list[float]]:
        if not self.api_key:
            raise EmbeddingError("GEMINI_API_KEY is not configured")

        def request() -> list[list[float]]:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=self.api_key)
                response = client.models.embed_content(
                    model=self.model,
                    contents=texts,
                    config=types.EmbedContentConfig(
                        task_type=task_type,
                        output_dimensionality=self.dimension,
                    ),
                )
                embeddings = getattr(response, "embeddings", None)
                if embeddings is None:
                    raise EmbeddingError("Gemini returned no embeddings")
                vectors = [list(getattr(item, "values", [])) for item in embeddings]
                if len(vectors) != len(texts):
                    raise EmbeddingError("Gemini returned the wrong number of vectors")
                return vectors
            except EmbeddingError:
                raise
            except Exception as exc:
                raise EmbeddingError("Gemini embedding request failed") from exc

        return await asyncio.to_thread(request)


def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.EMBEDDING_PROVIDER.strip().lower() != "gemini":
        raise EmbeddingError("Only the Gemini embedding provider is supported")
    return GeminiEmbeddingProvider(
        settings.EMBEDDING_MODEL,
        settings.GEMINI_API_KEY,
        settings.EMBEDDING_DIMENSION,
    )


async def embed_texts(
    texts: list[str],
    *,
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> list[list[float]]:
    if not texts or any(not text.strip() for text in texts):
        raise EmbeddingError("Embedding input must contain non-empty text")
    settings = get_settings()
    provider = get_embedding_provider()
    vectors: list[list[float]] = []
    batch_size = max(1, settings.EMBEDDING_BATCH_SIZE)
    for start in range(0, len(texts), batch_size):
        batch_texts = texts[start : start + batch_size]
        batch = await provider.embed(batch_texts, task_type=task_type)
        if len(batch) != len(batch_texts):
            raise EmbeddingError("Embedding provider returned the wrong number of vectors")
        vectors.extend(batch)
    if any(len(vector) != settings.EMBEDDING_DIMENSION for vector in vectors):
        raise EmbeddingError("Embedding vector dimension does not match configuration")
    return vectors
