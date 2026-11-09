"""Razorpay Standard Web Checkout endpoints."""

import asyncio
import hmac
import hashlib
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

import razorpay
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import PaymentOrder, PaymentWebhookEvent, User
from app.schemas.payment import (
    CreateOrderRequest,
    CreateOrderResponse,
    ReconcilePaymentFailureRequest,
    ReconcilePaymentFailureResponse,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
)
from app.services.transaction_service import record_payment_attempt, record_payment_transaction

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


def _client() -> razorpay.Client:
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment checkout is not configured.",
        )
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


@router.post("/create-order", response_model=CreateOrderResponse)
async def create_order(
    payload: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CreateOrderResponse:
    """Create a server-authorized Razorpay order."""
    client = _client()
    options = {
        "amount": payload.amount,
        "currency": payload.currency.upper(),
        "receipt": payload.receipt,
    }
    try:
        order = await asyncio.to_thread(client.order.create, options)
    except razorpay.errors.AuthenticationError as exc:
        logger.warning("Razorpay authentication failed while creating an order")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Payment provider authentication failed.",
        ) from exc
    except Exception as exc:
        logger.exception("Razorpay order creation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create payment order.",
        ) from exc
    db.add(
        PaymentOrder(
            user_id=current_user.id,
            provider_order_id=order["id"],
            amount=Decimal(order["amount"]) / Decimal(100),
            currency=order["currency"].upper(),
            status="created",
        )
    )
    await db.commit()
    return CreateOrderResponse(
        order_id=order["id"],
        amount=order["amount"],
        currency=order["currency"],
    )


@router.post("/verify-payment", response_model=VerifyPaymentResponse)
async def verify_payment(
    payload: VerifyPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerifyPaymentResponse:
    """Verify Razorpay's HMAC-SHA256 payment signature."""
    if not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment checkout is not configured.",
        )
    generated_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
        f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(
        generated_signature, payload.razorpay_signature
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment signature verification failed.",
        )
    payment_order = await _payment_order(db, payload.razorpay_order_id)
    if payment_order is None or payment_order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment order not found")
    client = _client()
    try:
        order = await asyncio.to_thread(client.order.fetch, payload.razorpay_order_id)
    except Exception as exc:
        logger.exception("Razorpay order lookup failed during payment verification")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to retrieve the verified payment order.",
        ) from exc

    await record_payment_transaction(
        db,
        current_user,
        provider_order_id=payload.razorpay_order_id,
        provider_payment_id=payload.razorpay_payment_id,
        amount=Decimal(order["amount"]) / Decimal(100),
        currency=order["currency"],
        occurred_at=datetime.now(timezone.utc),
    )
    return VerifyPaymentResponse(verified=True, message="Payment verified successfully.")


async def _payment_order(
    db: AsyncSession,
    provider_order_id: str,
) -> PaymentOrder | None:
    return await db.scalar(
        select(PaymentOrder).where(PaymentOrder.provider_order_id == provider_order_id)
    )


async def _record_failed_payment(
    db: AsyncSession,
    *,
    provider_order_id: str,
    payment: dict,
) -> bool:
    payment_order = await _payment_order(db, provider_order_id)
    if payment_order is None:
        return False
    await record_payment_attempt(
        db,
        user_id=payment_order.user_id,
        provider_order_id=provider_order_id,
        provider_payment_id=payment["id"],
        amount=Decimal(payment["amount"]) / Decimal(100),
        currency=payment["currency"],
        status="failed",
        payment_method=payment.get("method"),
        occurred_at=datetime.now(timezone.utc),
        failure_code=payment.get("error_code"),
        failure_description=payment.get("error_description"),
        failure_source=payment.get("error_source"),
        failure_step=payment.get("error_step"),
        failure_reason=payment.get("error_reason"),
    )
    return True


@router.post("/reconcile-failure", response_model=ReconcilePaymentFailureResponse)
async def reconcile_failure(
    payload: ReconcilePaymentFailureRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReconcilePaymentFailureResponse:
    """Reconcile a browser-reported failure with Razorpay's server-side API."""
    payment_order = await _payment_order(db, payload.razorpay_order_id)
    if payment_order is None or payment_order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment order not found")
    try:
        payment = await asyncio.to_thread(_client().payment.fetch, payload.razorpay_payment_id)
    except Exception as exc:
        logger.exception("Razorpay payment lookup failed during failure reconciliation")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Payment failure is pending provider verification.",
        ) from exc
    if payment.get("order_id") != payload.razorpay_order_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment order mismatch")
    if payment.get("status") != "failed":
        return ReconcilePaymentFailureResponse(
            status="pending",
            message="Payment status is pending provider reconciliation.",
        )
    await _record_failed_payment(db, provider_order_id=payload.razorpay_order_id, payment=payment)
    return ReconcilePaymentFailureResponse(
        status="failed",
        message="Verified failed payment recorded.",
    )


@router.post("/webhook")
async def webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Accept and process Razorpay payment events."""
    body = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Webhook is not configured")
    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook payload") from None

    event_id = request.headers.get("x-razorpay-event-id") or hashlib.sha256(body).hexdigest()
    existing = await db.scalar(
        select(PaymentWebhookEvent).where(PaymentWebhookEvent.provider_event_id == event_id)
    )
    if existing is not None:
        return {"status": "duplicate"}

    event_type = payload.get("event", "")
    event_record = PaymentWebhookEvent(
        provider_event_id=event_id,
        event_type=event_type,
        payload=payload,
        signature_valid=True,
    )
    db.add(event_record)
    await db.commit()
    try:
        entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        if event_type == "payment.failed" and entity.get("id") and entity.get("order_id"):
            await _record_failed_payment(
                db, provider_order_id=entity["order_id"], payment=entity
            )
        elif event_type in {"payment.captured", "payment.authorized"} and entity.get("id") and entity.get("order_id"):
            payment_order = await _payment_order(db, entity["order_id"])
            if payment_order is not None:
                await record_payment_attempt(
                    db,
                    user_id=payment_order.user_id,
                    provider_order_id=entity["order_id"],
                    provider_payment_id=entity["id"],
                    amount=Decimal(entity["amount"]) / Decimal(100),
                    currency=entity["currency"],
                    status="successful",
                    payment_method=entity.get("method"),
                    occurred_at=datetime.now(timezone.utc),
                )
        event_record.processed_at = datetime.now(timezone.utc)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        stored_event = await db.scalar(
            select(PaymentWebhookEvent).where(
                PaymentWebhookEvent.provider_event_id == event_id
            )
        )
        if stored_event is not None:
            stored_event.processing_error = str(exc)[:500]
            await db.commit()
        logger.exception("Razorpay webhook processing failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook processing failed") from exc
    return {"status": "processed"}
