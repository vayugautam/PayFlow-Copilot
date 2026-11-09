"""Dispute list response serialization tests."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.models import Dispute, User


class DisputeListSession:
    def __init__(self, user: User, dispute: Dispute):
        self.user = user
        self.dispute = dispute

    async def scalar(self, statement):
        if "count" in str(statement).lower():
            return 1
        return None

    async def scalars(self, statement):
        return [self.dispute]


def test_dispute_list_serializes_orm_items():
    user = User(id=uuid4(), email="owner@example.com", password_hash="hash", is_active=True)
    now = datetime.now(timezone.utc)
    dispute = Dispute(
        id=uuid4(),
        user_id=user.id,
        transaction_id=uuid4(),
        title="Payment dispute",
        description="Review this payment.",
        reason="OTHER",
        status="DRAFT",
        evidence=None,
        created_at=now,
        updated_at=now,
    )
    session = DisputeListSession(user, dispute)

    async def override_user():
        return user

    async def override_db():
        yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/api/v1/disputes?page=1&page_size=5")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["title"] == "Payment dispute"
