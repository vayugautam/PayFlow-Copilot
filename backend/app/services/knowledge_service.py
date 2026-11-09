"""Document extraction, chunking, ingestion, and ownership-scoped retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath
from uuid import UUID

from qdrant_client.http.models import PointStruct
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import KnowledgeDocument, User
from app.services.embedding_service import EmbeddingError, embed_texts
from app.services.qdrant_service import QdrantService, chunk_point_id, get_qdrant_service


class DocumentValidationError(ValueError):
    """Raised for unsupported or unusable document uploads."""


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int | None
    content: str


@dataclass(frozen=True)
class DocumentChunk:
    index: int
    page_number: int | None
    content: str


def normalize_text(value: str) -> str:
    value = value.replace("\x00", " ")
    return re.sub(r"[ \t]+\n", "\n", re.sub(r"\s+", " ", value)).strip()


def extract_document(filename: str, content_type: str, data: bytes) -> list[ExtractedPage]:
    suffix = PurePath(filename).suffix.lower()
    if suffix == ".txt":
        text = data.decode("utf-8-sig", errors="replace")
        normalized = normalize_text(text)
        if not normalized:
            raise DocumentValidationError("The text document is empty")
        return [ExtractedPage(None, normalized)]
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(data), strict=False)
            pages = [
                ExtractedPage(index + 1, normalize_text(page.extract_text() or ""))
                for index, page in enumerate(reader.pages)
            ]
        except Exception as exc:
            raise DocumentValidationError("The PDF could not be read") from exc
        pages = [page for page in pages if page.content]
        if not pages:
            raise DocumentValidationError("The PDF contains no extractable text")
        return pages
    raise DocumentValidationError("Only PDF and TXT documents are supported")


def chunk_pages(
    pages: list[ExtractedPage],
    *,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[DocumentChunk]:
    settings = get_settings()
    size = chunk_size or settings.KNOWLEDGE_CHUNK_SIZE
    overlap_size = overlap if overlap is not None else settings.KNOWLEDGE_CHUNK_OVERLAP
    if size <= 0 or overlap_size < 0 or overlap_size >= size:
        raise DocumentValidationError("Chunk overlap must be smaller than chunk size")
    chunks: list[DocumentChunk] = []
    for page in pages:
        start = 0
        while start < len(page.content):
            end = min(start + size, len(page.content))
            content = page.content[start:end].strip()
            if content:
                chunks.append(DocumentChunk(len(chunks), page.page_number, content))
            if end == len(page.content):
                break
            start = end - overlap_size
    if not chunks:
        raise DocumentValidationError("The document contains no usable text")
    return chunks


async def ingest_document(
    db: AsyncSession,
    user: User,
    *,
    filename: str,
    content_type: str,
    data: bytes,
    qdrant: QdrantService | None = None,
) -> KnowledgeDocument:
    settings = get_settings()
    if len(data) > settings.KNOWLEDGE_MAX_FILE_SIZE_BYTES:
        raise DocumentValidationError("The document exceeds the configured file size limit")
    pages = extract_document(filename, content_type, data)
    chunks = chunk_pages(pages)
    document = KnowledgeDocument(
        user_id=user.id,
        title=PurePath(filename).stem[:255] or "Untitled document",
        filename=filename[:255],
        content_type=content_type,
        size_bytes=len(data),
        status="processing",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    vector_store = qdrant or get_qdrant_service()
    try:
        vectors = await embed_texts(
            [chunk.content for chunk in chunks],
            task_type="RETRIEVAL_DOCUMENT",
        )
        points = [
            PointStruct(
                id=chunk_point_id(document.id, chunk.index),
                vector=vector,
                payload={
                    "chunk_id": f"{document.id}:{chunk.index}",
                    "document_id": str(document.id),
                    "user_id": str(user.id),
                    "document_title": document.title,
                    "filename": document.filename,
                    "chunk_index": chunk.index,
                    "page_number": chunk.page_number,
                    "content": chunk.content,
                    "source": {"filename": filename, "content_type": content_type},
                    "created_at": document.created_at.isoformat(),
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        await vector_store.upsert(points)
        document.chunk_count = len(chunks)
        document.status = "ready"
        from datetime import datetime, timezone

        document.ingested_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(document)
        return document
    except Exception:
        try:
            await vector_store.delete_document(document.id)
        except Exception:
            await db.rollback()
            raise
        else:
            await db.delete(document)
            await db.commit()
        raise


async def list_documents(
    db: AsyncSession, user: User, *, page: int, page_size: int
) -> tuple[list[KnowledgeDocument], int]:
    filters = [KnowledgeDocument.user_id == user.id]
    total = await db.scalar(select(func.count()).select_from(KnowledgeDocument).where(*filters))
    result = await db.scalars(
        select(KnowledgeDocument)
        .where(*filters)
        .order_by(KnowledgeDocument.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result), int(total or 0)


async def get_document(db: AsyncSession, user: User, document_id: UUID) -> KnowledgeDocument | None:
    return await db.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.user_id == user.id,
        )
    )


async def delete_document(
    db: AsyncSession, user: User, document: KnowledgeDocument, qdrant: QdrantService | None = None
) -> None:
    await (qdrant or get_qdrant_service()).delete_document(document.id, user.id)
    await db.delete(document)
    await db.commit()


async def retrieve(
    db: AsyncSession,
    user: User,
    query: str,
    top_k: int,
    document_id: UUID | None = None,
    qdrant: QdrantService | None = None,
) -> list[dict]:
    normalized_query = normalize_text(query)
    if not normalized_query:
        raise DocumentValidationError("The retrieval query is empty")
    vectors = await embed_texts([normalized_query], task_type="RETRIEVAL_QUERY")
    hits = await (qdrant or get_qdrant_service()).search(
        vectors[0], user.id, top_k, document_id
    )
    document_ids = {
        UUID(str(hit.payload["document_id"]))
        for hit in hits
        if hit.payload and hit.payload.get("document_id")
        and (document_id is None or hit.payload["document_id"] == str(document_id))
    }
    if not document_ids:
        return []
    documents = await db.scalars(
        select(KnowledgeDocument).where(
            KnowledgeDocument.user_id == user.id,
            KnowledgeDocument.id.in_(document_ids),
            KnowledgeDocument.status == "ready",
        )
    )
    by_id = {document.id: document for document in documents}
    results = []
    for hit in hits:
        payload = hit.payload or {}
        raw_document_id = payload.get("document_id")
        if not raw_document_id:
            continue
        try:
            doc_id = UUID(str(raw_document_id))
        except ValueError:
            continue
        if doc_id not in by_id or hit.score < get_settings().KNOWLEDGE_SIMILARITY_THRESHOLD:
            continue
        results.append(
            {
                "content": str(payload.get("content", "")),
                "score": float(hit.score),
                "document_id": doc_id,
                "chunk_id": str(payload.get("chunk_id", f"{doc_id}:{payload.get('chunk_index', 0)}")),
                "document_title": by_id[doc_id].title,
                "page_number": payload.get("page_number"),
                "chunk_index": int(payload.get("chunk_index", 0)),
                "filename": payload.get("filename", by_id[doc_id].filename),
                "source": payload.get("source"),
            }
        )
    return results[:top_k]
