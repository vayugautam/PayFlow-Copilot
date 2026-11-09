"""Focused tests for verified Razorpay failure ingestion."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.routes import payments
from app.core.config import get_settings
from app.db.session import get_db
from app.main import app
from app.models import PaymentOrder
from app.services.transaction_service import record_payment_attempt


class ScalarSession:
    def __init__(self, payment_order=None):
        self.payment_order = payment_order

    async def scalar(self, statement):
        if "payment_orders" in str(statement):
            return self.payment_order
        return None


class AttemptSession:
    def __init__(self):
        self.transactions = []
        self.pending = None

    async def scalar(self, statement):
        if "transactions" not in str(statement):
            return None
        params = statement.compile().params
        payment_id = next(
            (value for key, value in params.items() if "provider_payment_id" in key),
            None,
        )
        return next(
            (item for item in self.transactions if item.provider_payment_id == payment_id),
            None,
        )

    def add(self, transaction):
        self.pending = transaction

    async def commit(self):
        self.transactions.append(self.pending)
        self.pending = None

    async def refresh(self, transaction):
        return None


@pytest.mark.asyncio
async def test_failed_payment_maps_gateway_details(monkeypatch):
    user_id = uuid4()
    order = PaymentOrder(
        id=uuid4(),
        user_id=user_id,
        provider_order_id="order_1",
        amount=Decimal("100.00"),
        currency="INR",
        status="created",
    )
    recorder = AsyncMock()
    monkeypatch.setattr(payments, "record_payment_attempt", recorder)

    recorded = await payments._record_failed_payment(
        ScalarSession(order),
        provider_order_id="order_1",
        payment={
            "id": "pay_1",
            "amount": 10000,
            "currency": "INR",
            "method": "card",
            "error_code": "BAD_REQUEST_ERROR",
            "error_description": "Payment failed",
            "error_source": "customer",
            "error_step": "payment_authentication",
            "error_reason": "payment_failed",
        },
    )

    assert recorded is True
    recorder.assert_awaited_once()
    assert recorder.await_args.kwargs["user_id"] == user_id
    assert recorder.await_args.kwargs["failure_code"] == "BAD_REQUEST_ERROR"
    assert recorder.await_args.kwargs["failure_description"] == "Payment failed"


@pytest.mark.asyncio
async def test_unknown_provider_order_is_not_recorded(monkeypatch):
    recorder = AsyncMock()
    monkeypatch.setattr(payments, "record_payment_attempt", recorder)

    recorded = await payments._record_failed_payment(
        ScalarSession(),
        provider_order_id="unknown_order",
        payment={"id": "pay_1", "amount": 10000, "currency": "INR"},
    )

    assert recorded is False
    recorder.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_optional_failure_fields_are_preserved_as_null(monkeypatch):
    order = PaymentOrder(
        id=uuid4(), user_id=uuid4(), provider_order_id="order_2",
        amount=Decimal("100.00"), currency="INR", status="created",
    )
    recorder = AsyncMock()
    monkeypatch.setattr(payments, "record_payment_attempt", recorder)
    await payments._record_failed_payment(
        ScalarSession(order),
        provider_order_id="order_2",
        payment={"id": "pay_2", "amount": 10000, "currency": "INR"},
    )
    assert recorder.await_args.kwargs["failure_code"] is None
    assert recorder.await_args.kwargs["failure_reason"] is None


@pytest.mark.asyncio
async def test_duplicate_failure_event_is_idempotent():
    db = AttemptSession()
    args = {
        "user_id": uuid4(), "provider_order_id": "order_3",
        "provider_payment_id": "pay_3", "amount": Decimal("100.00"),
        "currency": "INR", "status": "failed", "payment_method": "card",
        "occurred_at": datetime.now(timezone.utc),
    }
    await record_payment_attempt(db, **args)
    await record_payment_attempt(db, **args)
    assert len(db.transactions) == 1


@pytest.mark.asyncio
async def test_capture_after_failure_updates_same_attempt_without_stale_failure():
    db = AttemptSession()
    args = {
        "user_id": uuid4(), "provider_order_id": "order_4",
        "provider_payment_id": "pay_4", "amount": Decimal("100.00"),
        "currency": "INR", "payment_method": "card",
        "occurred_at": datetime.now(timezone.utc),
    }
    await record_payment_attempt(db, status="failed", failure_code="DECLINED", **args)
    await record_payment_attempt(db, status="successful", **args)
    assert len(db.transactions) == 1
    assert db.transactions[0].status == "successful"
    assert db.transactions[0].failure_code is None


@pytest.mark.asyncio
async def test_payment_attempt_ownership_is_enforced():
    db = AttemptSession()
    first = {
        "user_id": uuid4(), "provider_order_id": "order_5",
        "provider_payment_id": "pay_5", "amount": Decimal("100.00"),
        "currency": "INR", "status": "failed", "payment_method": "card",
        "occurred_at": datetime.now(timezone.utc),
    }
    await record_payment_attempt(db, **first)
    with pytest.raises(ValueError, match="another user"):
        await record_payment_attempt(db, **{**first, "user_id": uuid4()})


def test_invalid_webhook_signature_is_rejected(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "webhook-secret")

    async def override_db():
        yield ScalarSession()

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).post(
            "/api/v1/payments/webhook",
            content=b'{"event":"payment.failed"}',
            headers={"x-razorpay-signature": "invalid"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
