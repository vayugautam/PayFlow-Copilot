"""Ownership-scoped transaction persistence services."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Transaction, User


async def create_transaction(
    db: AsyncSession,
    user: User,
    *,
    amount: Decimal,
    currency: str,
    status: str,
    merchant: str,
    description: str | None,
    failure_code: str | None,
    payment_method: str | None,
    occurred_at: datetime,
) -> Transaction:
    transaction = Transaction(
        user_id=user.id,
        amount=amount,
        currency=currency,
        status=status,
        merchant=merchant,
        description=description,
        failure_code=failure_code,
        payment_method=payment_method,
        occurred_at=occurred_at,
    )
    db.add(transaction)
    await db.commit()
    await db.refresh(transaction)
    return transaction


async def record_payment_attempt(
    db: AsyncSession,
    *,
    user_id: UUID,
    provider_order_id: str,
    provider_payment_id: str,
    amount: Decimal,
    currency: str,
    status: str,
    payment_method: str | None,
    occurred_at: datetime,
    failure_code: str | None = None,
    failure_description: str | None = None,
    failure_source: str | None = None,
    failure_step: str | None = None,
    failure_reason: str | None = None,
) -> Transaction:
    existing = await db.scalar(
        select(Transaction).where(Transaction.provider_payment_id == provider_payment_id)
    )
    if existing is not None:
        if existing.user_id != user_id:
            raise ValueError("Payment attempt belongs to another user")
        if status == "successful" and existing.status != "successful":
            existing.status = "successful"
            existing.failure_code = None
            existing.failure_description = None
            existing.failure_source = None
            existing.failure_step = None
            existing.failure_reason = None
        return existing

    transaction = Transaction(
        user_id=user_id,
        amount=amount,
        currency=currency.upper(),
        status=status,
        merchant="Razorpay",
        description=f"Razorpay payment {provider_payment_id}",
        failure_code=failure_code,
        payment_method=payment_method or "razorpay",
        provider_order_id=provider_order_id,
        provider_payment_id=provider_payment_id,
        failure_description=failure_description,
        failure_source=failure_source,
        failure_step=failure_step,
        failure_reason=failure_reason,
        occurred_at=occurred_at,
    )
    db.add(transaction)
    await db.commit()
    await db.refresh(transaction)
    return transaction


async def record_payment_transaction(
    db: AsyncSession,
    user: User,
    *,
    provider_order_id: str,
    provider_payment_id: str,
    amount: Decimal,
    currency: str,
    occurred_at: datetime,
) -> Transaction:
    return await record_payment_attempt(
        db,
        user_id=user.id,
        provider_order_id=provider_order_id,
        provider_payment_id=provider_payment_id,
        amount=amount,
        currency=currency,
        status="successful",
        payment_method="razorpay",
        occurred_at=occurred_at,
    )


async def get_transaction_by_id(
    db: AsyncSession,
    user: User,
    transaction_id: UUID,
) -> Transaction | None:
    return await db.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user.id,
        )
    )


async def get_user_transactions(
    db: AsyncSession,
    user: User,
    *,
    page: int,
    page_size: int,
    status: str | None = None,
    currency: str | None = None,
    merchant: str | None = None,
) -> tuple[list[Transaction], int]:
    filters = [Transaction.user_id == user.id]
    if status:
        filters.append(Transaction.status == status)
    if currency:
        filters.append(Transaction.currency == currency.upper())
    if merchant:
        filters.append(Transaction.merchant.ilike(f"%{merchant.strip()}%"))

    total = await db.scalar(
        select(func.count()).select_from(Transaction).where(*filters)
    )
    result = await db.scalars(
        select(Transaction)
        .where(*filters)
        .order_by(Transaction.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result), int(total or 0)
