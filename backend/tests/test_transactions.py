"""Transaction API tests using isolated in-memory session doubles."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models import Transaction, User


class TransactionSession:
    def __init__(self, user: User, transactions: list[Transaction] | None = None):
        self.user = user
        self.transactions = transactions or []
        self.pending = None

    async def scalar(self, statement):
        if "count" in str(statement._raw_columns[0]).lower():
            return len(self._filtered(statement))
        transaction_id = self._value_for(statement, "id")
        if transaction_id is not None:
            return next(
                (item for item in self._filtered(statement) if item.id == transaction_id),
                None,
            )
        return None

    async def scalars(self, statement):
        items = self._filtered(statement)
        items.sort(key=lambda item: item.created_at, reverse=True)
        offset = statement._offset_clause.value if statement._offset_clause is not None else 0
        limit = statement._limit_clause.value if statement._limit_clause is not None else len(items)
        return items[offset : offset + limit]

    def _value_for(self, statement, name):
        for bind in statement.compile().params:
            if name in bind:
                return statement.compile().params[bind]
        return None

    def _filtered(self, statement):
        items = list(self.transactions)
        params = statement.compile().params
        if "status_1" in params:
            items = [item for item in items if item.status == params["status_1"]]
        if "currency_1" in params:
            items = [item for item in items if item.currency == params["currency_1"]]
        if "merchant_1" in params:
            items = [item for item in items if params["merchant_1"].strip("%").lower() in item.merchant.lower()]
        if "id_1" in params:
            items = [item for item in items if item.id == params["id_1"]]
        return [item for item in items if item.user_id == self.user.id]

    def add(self, transaction):
        self.pending = transaction

    async def commit(self):
        now = datetime.now(timezone.utc)
        self.pending.id = self.pending.id or uuid4()
        self.pending.created_at = now
        self.pending.updated_at = now
        self.transactions.append(self.pending)
        self.pending = None

    async def refresh(self, transaction):
        return None


@pytest.fixture
def transaction_client():
    user = User(
        id=uuid4(),
        email="owner@example.com",
        password_hash="hash",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    transactions = [
        Transaction(
            id=uuid4(),
            user_id=user.id,
            amount=Decimal("10.00"),
            currency="USD",
            status="successful",
            merchant="Acme Coffee",
            occurred_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
        Transaction(
            id=uuid4(),
            user_id=user.id,
            amount=Decimal("20.50"),
            currency="EUR",
            status="failed",
            merchant="Contoso Market",
            occurred_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
    ]
    session = TransactionSession(user, transactions)

    async def override_user():
        return user

    async def override_db():
        yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    yield TestClient(app), user, session
    app.dependency_overrides.clear()


def test_transaction_creation_and_decimal_precision(transaction_client):
    client, user, session = transaction_client
    response = client.post(
        "/api/v1/transactions",
        json={
            "amount": "42.35",
            "currency": "usd",
            "status": "pending",
            "merchant": "Globex Travel",
            "occurred_at": "2026-11-07T12:00:00Z",
        },
    )
    assert response.status_code == 201
    assert response.json()["amount"] == "42.35"
    assert session.transactions[-1].user_id == user.id


def test_listing_pagination_and_filters(transaction_client):
    client, _, _ = transaction_client
    response = client.get(
        "/api/v1/transactions?page=1&page_size=1&currency=usd&merchant=coffee"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["page_size"] == 1
    assert body["items"][0]["merchant"] == "Acme Coffee"


def test_detail_missing_and_cross_user_access(transaction_client):
    client, _, session = transaction_client
    missing = client.get(f"/api/v1/transactions/{uuid4()}")
    assert missing.status_code == 404

    other = User(
        id=uuid4(),
        email="other@example.com",
        password_hash="hash",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    foreign = Transaction(
        id=uuid4(),
        user_id=other.id,
        amount=Decimal("5.00"),
        currency="USD",
        status="successful",
        merchant="Private Merchant",
        occurred_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.transactions.append(foreign)
    assert client.get(f"/api/v1/transactions/{foreign.id}").status_code == 404


@pytest.mark.parametrize(
    "field,value",
    [("amount", "0"), ("currency", "US"), ("status", "unknown")],
)
def test_invalid_transaction_input(transaction_client, field, value):
    payload = {
        "amount": "10.00",
        "currency": "USD",
        "status": "successful",
        "merchant": "Acme",
        "occurred_at": "2026-11-07T12:00:00Z",
        field: value,
    }
    assert transaction_client[0].post("/api/v1/transactions", json=payload).status_code == 422


def test_unauthorized_transaction_request():
    app.dependency_overrides.clear()
    client = TestClient(app)
    assert client.get("/api/v1/transactions").status_code == 401
