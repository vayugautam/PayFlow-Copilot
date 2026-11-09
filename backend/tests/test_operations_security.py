import logging
from datetime import timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.observability import (
    RequestContextFilter,
    authenticated_rate_limit_dependency,
    rate_limiter,
    safe_log_value,
)
from app.core.security import create_access_token, decode_access_token
from app.main import app


def test_request_id_and_security_headers_are_returned():
    response = TestClient(app).get("/", headers={"X-Request-ID": "diagnostic-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "diagnostic-123"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_invalid_request_id_is_replaced():
    response = TestClient(app).get("/", headers={"X-Request-ID": "bad value"})

    assert response.headers["X-Request-ID"]
    assert response.headers["X-Request-ID"] != "bad value"


def test_structured_log_filter_supplies_request_id_without_sensitive_values(caplog):
    record = logging.LogRecord("test", logging.INFO, "", 0, "request_complete", (), None)
    RequestContextFilter().filter(record)

    assert record.request_id == "-"
    assert "password" not in str(record.__dict__).lower()
    assert safe_log_value("password=secret") == "[REDACTED]"


def test_rate_limiter_rejects_after_limit():
    assert rate_limiter.check("test", 1, 60)
    assert not rate_limiter.check("test", 1, 60)


@pytest.mark.asyncio
async def test_authenticated_rate_limit_uses_user_subject():
    dependency = authenticated_rate_limit_dependency("chat", 1, 60)
    token = create_access_token("same-user")

    def request():
        return __import__("starlette.requests", fromlist=["Request"]).Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/chat",
                "headers": [(b"authorization", f"Bearer {token}".encode())],
                "client": ("127.0.0.1", 1),
                "query_string": b"",
                "server": ("testserver", 80),
                "scheme": "http",
            }
        )

    await dependency(request())
    with pytest.raises(HTTPException) as exc_info:
        await dependency(request())
    assert getattr(exc_info.value, "status_code", None) == 429


def test_production_settings_reject_insecure_values():
    with pytest.raises(ValidationError, match="cryptographically secure"):
        Settings(
            APP_ENV="production",
            DEBUG=False,
            SECRET_KEY="secret",
            DATABASE_URL="postgresql+psycopg://user:pass@db:5432/payflow",
            CORS_ORIGINS=["https://app.example.com"],
        )


def test_production_settings_reject_local_database():
    with pytest.raises(ValidationError, match="localhost"):
        Settings(
            APP_ENV="production",
            DEBUG=False,
            SECRET_KEY="a" * 64,
            DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/payflow",
            CORS_ORIGINS=["https://app.example.com"],
        )


def test_expired_jwt_is_rejected():
    token = create_access_token("subject", expires_delta=timedelta(seconds=-1))

    with pytest.raises(Exception):
        decode_access_token(token)
