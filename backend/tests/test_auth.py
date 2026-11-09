"""Authentication API tests using an isolated in-memory session double."""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.security import create_access_token, decode_access_token, get_password_hash
from app.db.session import get_db
from app.main import app
from app.models import User


class InMemorySession:
    def __init__(self):
        self.users: dict[UUID, User] = {}
        self.pending: User | None = None

    async def scalar(self, statement):
        criterion = statement.whereclause
        value = criterion.right.value
        if criterion.left.name == "email":
            return next((u for u in self.users.values() if u.email == value), None)
        return self.users.get(value)

    def add(self, user: User):
        self.pending = user

    async def commit(self):
        assert self.pending is not None
        if self.pending.id is None:
            self.pending.id = uuid4()
        if self.pending.is_active is None:
            self.pending.is_active = True
        now = datetime.now(timezone.utc)
        self.pending.created_at = now
        self.pending.updated_at = now
        self.users[self.pending.id] = self.pending
        self.pending = None

    async def refresh(self, user: User):
        return None

    async def rollback(self):
        self.pending = None


@pytest.fixture
def client():
    session = InMemorySession()

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    yield TestClient(app), session
    app.dependency_overrides.clear()


def test_register_normalizes_email_and_never_returns_hash(client):
    test_client, session = client

    response = test_client.post(
        "/api/v1/auth/register",
        json={"email": "  USER@Example.COM ", "password": "correct-password"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "user@example.com"
    assert "password_hash" not in body
    user = next(iter(session.users.values()))
    assert user.password_hash != "correct-password"
    assert user.password_hash.startswith("$argon2id$")


def test_cors_preflight_allows_local_frontend(client):
    response = client[0].options(
        "/api/v1/chat/conversations",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "POST" in response.headers["access-control-allow-methods"]


def test_register_duplicate_email_returns_conflict(client):
    test_client, _ = client
    payload = {"email": "user@example.com", "password": "correct-password"}

    assert test_client.post("/api/v1/auth/register", json=payload).status_code == 201
    response = test_client.post(
        "/api/v1/auth/register",
        json={"email": " USER@example.com ", "password": "another-password"},
    )

    assert response.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": "correct-password"},
        {"email": "user@example.com", "password": "short"},
    ],
)
def test_register_validates_input(client, payload):
    response = client[0].post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422


def test_login_returns_decodable_token_and_generic_failures(client):
    test_client, _ = client
    credentials = {"email": "user@example.com", "password": "correct-password"}
    test_client.post("/api/v1/auth/register", json=credentials)

    success = test_client.post("/api/v1/auth/login", json=credentials)
    assert success.status_code == 200
    assert success.json()["token_type"] == "bearer"
    assert decode_access_token(success.json()["access_token"])["sub"]

    invalid_password = test_client.post(
        "/api/v1/auth/login",
        json={"email": credentials["email"], "password": "wrong-password"},
    )
    unknown_email = test_client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "wrong-password"},
    )
    assert invalid_password.status_code == unknown_email.status_code == 401
    assert invalid_password.json() == unknown_email.json()


def test_login_rate_limit_returns_safe_429(client):
    test_client, _ = client
    payload = {"email": "missing@example.com", "password": "wrong-password"}

    responses = [test_client.post("/api/v1/auth/login", json=payload) for _ in range(11)]

    assert [response.status_code for response in responses[:10]] == [401] * 10
    assert responses[10].status_code == 429
    assert responses[10].json()["detail"] == "Too many requests. Please retry later."


def test_me_accepts_valid_token_and_returns_public_fields(client):
    test_client, session = client
    registered = test_client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "correct-password"},
    ).json()
    token = create_access_token(registered["id"])

    response = test_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert set(response.json()) == {"id", "email", "is_active", "created_at"}
    assert len(session.users) == 1


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "Bearer malformed",
        f"Bearer {create_access_token(uuid4(), expires_delta=timedelta(seconds=-1))}",
    ],
)
def test_me_rejects_missing_malformed_and_expired_tokens(client, authorization):
    headers = {} if authorization is None else {"Authorization": authorization}

    response = client[0].get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_rejects_invalid_uuid_and_inactive_or_deleted_users(client):
    test_client, session = client
    invalid_uuid_token = create_access_token("not-a-uuid")
    assert test_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {invalid_uuid_token}"},
    ).status_code == 401

    user = User(
        id=uuid4(),
        email="inactive@example.com",
        password_hash=get_password_hash("correct-password"),
        is_active=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.users[user.id] = user
    inactive_token = create_access_token(user.id)
    assert test_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {inactive_token}"},
    ).status_code == 401

    deleted_token = create_access_token(uuid4())
    assert test_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {deleted_token}"},
    ).status_code == 401
