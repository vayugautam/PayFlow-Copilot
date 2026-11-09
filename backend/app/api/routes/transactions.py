"""Authenticated transaction API routes."""

from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.transaction import (
    TRANSACTION_STATUSES,
    TransactionCreate,
    TransactionAnalysisResponse,
    TransactionListResponse,
    TransactionResponse,
)
from app.services.transaction_service import (
    create_transaction,
    get_transaction_by_id,
    get_user_transactions,
)
from app.services.payment_intelligence import analyze_transaction

router = APIRouter()


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create(
    payload: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await create_transaction(db, current_user, **payload.model_dump())


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    merchant: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    normalized_status = status_filter.lower() if status_filter else None
    if normalized_status and normalized_status not in TRANSACTION_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported transaction status")
    items, total = await get_user_transactions(
        db,
        current_user,
        page=page,
        page_size=page_size,
        status=normalized_status,
        currency=currency,
        merchant=merchant,
    )
    return TransactionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size) if total else 0,
    )


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get(
    transaction_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    transaction = await get_transaction_by_id(db, current_user, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.get(
    "/{transaction_id}/analysis",
    response_model=TransactionAnalysisResponse,
)
async def analysis(
    transaction_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionAnalysisResponse:
    transaction = await get_transaction_by_id(db, current_user, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return analyze_transaction(transaction)
