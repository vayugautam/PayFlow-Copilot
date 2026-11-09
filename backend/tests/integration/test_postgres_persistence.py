"""PostgreSQL-backed persistence and migration verification."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.models import KnowledgeDocument
from app.services.audit_service import list_events
from app.services.auth_service import authenticate_user, register_user
from app.services.conversation_service import add_message, create_conversation, list_messages
from app.services.dispute_service import confirm_dispute, create_draft
from app.services.payment_intelligence import analyze_transaction
from app.services.transaction_service import (
    create_transaction,
    get_transaction_by_id,
    get_user_transactions,
)

pytestmark = pytest.mark.integration


async def _user(db, email: str | None = None):
    return await register_user(db, email or f"{uuid4()}@example.com", "correct-password")


async def _transaction(db, user, status="failed"):
    return await create_transaction(
        db, user, amount=Decimal("25.00"), currency="USD", status=status,
        merchant="Integration Shop", description="Integration transaction",
        failure_code="TIMEOUT" if status == "failed" else None,
        payment_method="card", occurred_at=datetime.now(timezone.utc),
    )


async def test_migrations_register_models_and_constraints(integration_db):
    table_names = set()

    async_connection = await integration_db.connection()

    def collect(connection):
        table_names.update(inspect(connection).get_table_names())

    await async_connection.run_sync(collect)
    assert {
        "users", "transactions", "knowledge_documents", "conversations",
        "messages", "disputes", "audit_logs", "payment_orders",
        "payment_webhook_events", "alembic_version",
    } <= table_names
    revision = (await integration_db.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
    assert revision == "20261109_08"
    assert {
        "users",
        "transactions",
        "knowledge_documents",
        "conversations",
        "messages",
        "disputes",
        "audit_logs",
        "payment_orders",
        "payment_webhook_events",
    } <= set(Base.metadata.tables)
    indexes = await integration_db.execute(
        text(
            "SELECT indexname FROM pg_indexes "
            "WHERE schemaname = current_schema() AND tablename = 'disputes'"
        )
    )
    assert "uq_disputes_active_transaction_reason" in {row[0] for row in indexes}


async def test_auth_registration_duplicate_login_and_inactive_user(integration_db):
    email = f"{uuid4()}@example.com"
    user = await register_user(integration_db, email, "correct-password")
    assert user.password_hash != "correct-password"
    assert await authenticate_user(integration_db, email, "correct-password")
    assert await authenticate_user(integration_db, email, "wrong-password") is None
    with pytest.raises(Exception):
        await register_user(integration_db, email, "another-password")
    user.is_active = False
    await integration_db.commit()
    assert await authenticate_user(integration_db, email, "correct-password") is None


async def test_transactions_persist_filter_page_analysis_and_ownership(integration_db):
    owner = await _user(integration_db)
    other = await _user(integration_db)
    transaction = await _transaction(integration_db, owner)
    await _transaction(integration_db, owner, "successful")
    items, total = await get_user_transactions(integration_db, owner, page=1, page_size=1, status="failed")
    assert total == 1
    assert items[0].id == transaction.id
    assert analyze_transaction(transaction).retry_eligibility.value == "verify_status_first"
    assert await get_transaction_by_id(integration_db, other, transaction.id) is None


async def test_knowledge_metadata_ownership_and_delete(integration_db):
    owner = await _user(integration_db)
    other = await _user(integration_db)
    document = KnowledgeDocument(
        user_id=owner.id, title="Policy", filename="policy.txt",
        content_type="text/plain", size_bytes=10, status="ready",
    )
    integration_db.add(document)
    await integration_db.commit()
    assert await integration_db.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document.id, KnowledgeDocument.user_id == other.id
        )
    ) is None
    await integration_db.delete(document)
    await integration_db.commit()
    assert await integration_db.get(KnowledgeDocument, document.id) is None


async def test_conversations_messages_order_and_ownership(integration_db):
    owner = await _user(integration_db)
    other = await _user(integration_db)
    conversation = await create_conversation(integration_db, owner, "Integration chat")
    first = await add_message(integration_db, conversation, role="user", content="First")
    second = await add_message(integration_db, conversation, role="assistant", content="Second")
    messages = await list_messages(integration_db, conversation.id)
    assert [message.id for message in messages] == [first.id, second.id]
    from app.models import Conversation
    assert await integration_db.scalar(
        select(Conversation).where(
            Conversation.id == conversation.id, Conversation.user_id == other.id
        )
    ) is None


async def test_dispute_audit_persistence_and_confirmation(integration_db, monkeypatch):
    owner = await _user(integration_db)
    transaction = await _transaction(integration_db, owner)
    policy_id = uuid4()

    async def fake_retrieve(*args, **kwargs):
        return [{"document_id": policy_id, "document_title": "Refund policy",
                 "page_number": 1, "chunk_index": 0,
                 "content": "Review failed payments within five days."}]

    class FakeCompletion:
        content = (
            '{"title":"Payment review","reason":"OTHER","description":"Review requested.",'
            '"evidence_checklist":["Confirm receipt"],"supporting_policy_evidence":["Review policy"],'
            '"evidence_references":[{"document_id":"%s","document_title":"Refund policy",'
            '"page_number":1,"chunk_index":0}],"evidence_support":"SUPPORTED",'
            '"missing_information":[]}' % policy_id
        )

    class FakeGroq:
        async def complete(self, *args, **kwargs):
            return FakeCompletion()

    monkeypatch.setattr("app.services.dispute_service.retrieve", fake_retrieve)
    monkeypatch.setattr("app.services.dispute_service.GroqLLMClient", FakeGroq)
    dispute = await create_draft(integration_db, owner, transaction.id, "Please review")
    assert dispute.status == "DRAFT"
    assert dispute.evidence["user_review_required"] is True
    confirmed = await confirm_dispute(integration_db, owner, dispute)
    assert confirmed.status == "SUBMITTED"
    events, total = await list_events(integration_db, owner, page=1, page_size=20)
    assert total >= 2
    assert {event.action for event in events} >= {"DISPUTE_DRAFT_CREATED", "DISPUTE_CONFIRMED"}


async def test_active_dispute_unique_constraint_is_postgres_enforced(integration_db):
    owner = await _user(integration_db)
    transaction = await _transaction(integration_db, owner)
    from app.models import Dispute
    now = datetime.now(timezone.utc)
    integration_db.add_all([
        Dispute(id=uuid4(), user_id=owner.id, transaction_id=transaction.id,
                title="First", description="First", reason="OTHER", status="DRAFT",
                created_at=now, updated_at=now),
        Dispute(id=uuid4(), user_id=owner.id, transaction_id=transaction.id,
                title="Second", description="Second", reason="OTHER", status="DRAFT",
                created_at=now, updated_at=now),
    ])
    with pytest.raises(IntegrityError):
        await integration_db.commit()
    await integration_db.rollback()
