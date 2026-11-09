"""Authenticated dispute-management and audit-log routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.dispute import (
    AuditLogPage, DisputeDraftRequest, DisputePage, DisputeResponse, DisputeUpdateRequest,
)
from app.services.audit_service import list_events
from app.services.dispute_service import (
    DisputeError, DisputeNotFound, InvalidDisputeTransition,
    cancel_dispute, confirm_dispute, create_draft, get_owned_dispute,
    list_owned_disputes, update_draft,
)
from app.services.llm_service import LLMError

router = APIRouter()


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Dispute not found")


@router.post("/drafts", response_model=DisputeResponse, status_code=status.HTTP_201_CREATED)
async def draft(
    payload: DisputeDraftRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await create_draft(db, current_user, payload.transaction_id, payload.user_claim, payload.conversation_id)
    except DisputeNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (DisputeError, LLMError) as exc:
        await db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("", response_model=DisputePage)
async def list_disputes(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    items, total = await list_owned_disputes(db, current_user, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/audit-logs", response_model=AuditLogPage)
async def audit_logs(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    entity_type: str | None = None, entity_id: UUID | None = None, action: str | None = None,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    items, total = await list_events(db, current_user, page=page, page_size=page_size,
                                     entity_type=entity_type, entity_id=entity_id, action=action)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{dispute_id}", response_model=DisputeResponse)
async def detail(dispute_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    dispute = await get_owned_dispute(db, current_user, dispute_id)
    if dispute is None:
        raise _not_found()
    return dispute


@router.patch("/{dispute_id}", response_model=DisputeResponse)
async def update(
    dispute_id: UUID, payload: DisputeUpdateRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    dispute = await get_owned_dispute(db, current_user, dispute_id)
    if dispute is None:
        raise _not_found()
    try:
        return await update_draft(db, current_user, dispute, payload.model_dump(exclude_unset=True))
    except InvalidDisputeTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{dispute_id}/confirm", response_model=DisputeResponse)
async def confirm(dispute_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    dispute = await get_owned_dispute(db, current_user, dispute_id)
    if dispute is None:
        raise _not_found()
    try:
        return await confirm_dispute(db, current_user, dispute)
    except InvalidDisputeTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{dispute_id}/cancel", response_model=DisputeResponse)
async def cancel(dispute_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    dispute = await get_owned_dispute(db, current_user, dispute_id)
    if dispute is None:
        raise _not_found()
    try:
        return await cancel_dispute(db, current_user, dispute)
    except InvalidDisputeTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
