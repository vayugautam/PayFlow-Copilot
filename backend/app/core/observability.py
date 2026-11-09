"""Request correlation, redacted structured logging, and local rate limiting."""

from __future__ import annotations

import logging
import re
import threading
import time
from collections import defaultdict, deque
from uuid import UUID, uuid4

from fastapi import HTTPException, Request, status
from jwt.exceptions import InvalidTokenError

from app.core.security import decode_access_token

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SENSITIVE_KEYS = {"password", "token", "authorization", "api_key", "secret", "cvv", "card_number"}


def request_id_from(request: Request) -> str:
    supplied = request.headers.get("X-Request-ID", "")
    return supplied if REQUEST_ID_PATTERN.fullmatch(supplied) else str(uuid4())


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(record, "request_id", "-")
        return True


def safe_log_value(value: object) -> str:
    text = str(value)
    return "[REDACTED]" if any(key in text.lower() for key in _SENSITIVE_KEYS) else text


class InMemoryRateLimiter:
    """Fixed-window limiter for one process; use shared storage when scaled out."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - window_seconds:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


rate_limiter = InMemoryRateLimiter()


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit_dependency(bucket: str, limit: int, window_seconds: int):
    async def dependency(request: Request) -> None:
        key = f"{bucket}:{client_key(request)}"
        if not rate_limiter.check(key, limit, window_seconds):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please retry later.",
                headers={"Retry-After": str(window_seconds)},
            )

    return dependency


def authenticated_rate_limit_dependency(bucket: str, limit: int, window_seconds: int):
    async def dependency(request: Request) -> None:
        # Decode only the subject for a stable per-user bucket; token material
        # is never logged or returned.
        authorization = request.headers.get("Authorization", "")
        identity = client_key(request)
        if authorization.lower().startswith("bearer "):
            try:
                identity = f"user:{decode_access_token(authorization[7:])['sub']}"
            except (InvalidTokenError, KeyError, TypeError):
                pass
        if not rate_limiter.check(f"{bucket}:{identity}", limit, window_seconds):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please retry later.",
                headers={"Retry-After": str(window_seconds)},
            )

    return dependency
