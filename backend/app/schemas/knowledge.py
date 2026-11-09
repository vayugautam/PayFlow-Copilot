"""Knowledge document API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    filename: str
    content_type: str
    size_bytes: int
    chunk_count: int
    status: str
    error_message: str | None = None
    created_at: datetime
    ingested_at: datetime | None = None


class KnowledgeDocumentListResponse(BaseModel):
    items: list[KnowledgeDocumentResponse]
    total: int
    page: int
    page_size: int


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=50)
    document_id: UUID | None = None


class RetrievalResult(BaseModel):
    content: str
    score: float
    document_id: UUID
    document_title: str
    filename: str
    page_number: int | None = None
    chunk_index: int
    source: dict[str, str] | str | None = None


class RetrievalResponse(BaseModel):
    items: list[RetrievalResult]
