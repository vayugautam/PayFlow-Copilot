"""Authenticated knowledge document upload and retrieval routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import KnowledgeDocument, User
from app.schemas.knowledge import (
    KnowledgeDocumentListResponse,
    KnowledgeDocumentResponse,
    RetrievalRequest,
    RetrievalResponse,
)
from app.services.embedding_service import EmbeddingError
from app.services.knowledge_service import (
    DocumentValidationError,
    delete_document,
    get_document,
    ingest_document,
    list_documents,
    retrieve,
)
from app.services.qdrant_service import QdrantConfigurationError
from app.core.observability import authenticated_rate_limit_dependency

router = APIRouter()


@router.post(
    "/documents",
    response_model=KnowledgeDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(authenticated_rate_limit_dependency("document_upload", get_settings().DOCUMENT_RATE_LIMIT, get_settings().RATE_LIMIT_WINDOW_SECONDS))],
)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    filename = file.filename or ""
    content_type = file.content_type or "application/octet-stream"
    if not filename.lower().endswith((".pdf", ".txt")):
        raise HTTPException(status_code=415, detail="Only PDF and TXT documents are supported")
    if content_type not in {"application/pdf", "text/plain", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="The uploaded MIME type is not supported")
    data = await file.read()
    if len(data) > settings.KNOWLEDGE_MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="The document exceeds the configured file size limit")
    try:
        return await ingest_document(
            db, current_user, filename=filename, content_type=content_type, data=data
        )
    except DocumentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (EmbeddingError, QdrantConfigurationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/documents", response_model=KnowledgeDocumentListResponse)
async def documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await list_documents(db, current_user, page=page, page_size=page_size)
    return KnowledgeDocumentListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentResponse)
async def document_detail(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    document = await get_document(db, current_user, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    document = await get_document(db, current_user, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        await delete_document(db, current_user, document)
    except QdrantConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/retrieve", response_model=RetrievalResponse)
async def retrieve_documents(
    request: RetrievalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        if request.document_id is not None:
            document = await get_document(db, current_user, request.document_id)
            if document is None:
                raise HTTPException(status_code=404, detail="Document not found")
        items = await retrieve(
            db, current_user, request.query, request.top_k, request.document_id
        )
    except DocumentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (EmbeddingError, QdrantConfigurationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return RetrievalResponse(items=items)
