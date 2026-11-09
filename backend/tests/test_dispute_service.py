"""Regression tests for dispute draft persistence."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models import Transaction, User
from app.services import dispute_service


class DraftSession:
    def __init__(self, user, transaction):
        self.user = user
        self.transaction = transaction
        self.pending = None

    async def scalar(self, statement):
        text = str(statement)
        if "transactions" in text:
            return self.transaction
        return None

    def add(self, value):
        self.pending = value

    async def flush(self):
        if self.pending is not None and self.pending.id is None:
            self.pending.id = uuid4()

    async def commit(self):
        return None

    async def refresh(self, value):
        value.created_at = value.created_at or datetime.now(timezone.utc)
        value.updated_at = value.updated_at or datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_create_draft_persists_generated_title(monkeypatch):
    user = User(id=uuid4(), email="owner@example.com", password_hash="hash", is_active=True)
    transaction = Transaction(
        id=uuid4(),
        user_id=user.id,
        amount=Decimal("100.00"),
        currency="INR",
        status="failed",
        merchant="Razorpay",
        occurred_at=datetime.now(timezone.utc),
    )
    db = DraftSession(user, transaction)

    async def retrieve_policy(*args):
        return []

    class FakeLLM:
        async def complete(self, *args):
            return type(
                "Completion",
                (),
                {
                    "content": json.dumps(
                        {
                            "title": "Payment failed",
                            "reason": "OTHER",
                            "description": "Review this failed payment.",
                            "evidence_checklist": ["Payment receipt"],
                            "evidence_support": "INSUFFICIENT_EVIDENCE",
                            "supporting_policy_evidence": [],
                            "evidence_references": [],
                            "missing_information": [],
                        }
                    )
                },
            )()

    monkeypatch.setattr(dispute_service, "retrieve", retrieve_policy)
    monkeypatch.setattr(dispute_service, "GroqLLMClient", FakeLLM)
    async def record_event(*args, **kwargs):
        return None

    monkeypatch.setattr(dispute_service, "record_event", record_event)

    dispute = await dispute_service.create_draft(
        db, user, transaction.id, "Please review this failed payment."
    )

    assert dispute.title == "Payment failed"
