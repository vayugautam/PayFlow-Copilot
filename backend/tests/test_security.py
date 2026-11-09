"""Unit tests for password hashing and JWT security utilities."""

from datetime import timedelta
from uuid import uuid4
import warnings

import jwt
import pytest
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidTokenError,
)
from jwt.warnings import InsecureKeyLengthWarning

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)

TEST_SIGNING_KEY = "test-signing-key-with-at-least-64-bytes-for-hmac-security"


def test_password_hash_is_not_plaintext():
    password = "correct horse battery staple"
    hashed = get_password_hash(password)

    assert hashed != password
    assert hashed.startswith("$argon2id$")


def test_same_password_gets_unique_hashes():
    password = "correct horse battery staple"

    assert get_password_hash(password) != get_password_hash(password)


def test_password_verification():
    hashed = get_password_hash("correct password")

    assert verify_password("correct password", hashed)
    assert not verify_password("wrong password", hashed)


def test_malformed_password_hash_is_rejected_safely():
    assert verify_password("password", "not-a-valid-password-hash") is False


def test_valid_jwt_contains_expected_claims():
    subject = uuid4()
    token = create_access_token(subject)
    payload = decode_access_token(token)

    assert set(payload) == {"sub", "iat", "exp"}
    assert payload["sub"] == str(subject)
    assert isinstance(payload["iat"], int)
    assert isinstance(payload["exp"], int)
    assert payload["exp"] > payload["iat"]


def test_custom_jwt_expiration():
    token = create_access_token("subject", expires_delta=timedelta(seconds=90))
    payload = decode_access_token(token)

    assert payload["exp"] - payload["iat"] == 90


def test_expired_token_is_rejected():
    token = create_access_token("subject", expires_delta=timedelta(seconds=-1))

    with pytest.raises(ExpiredSignatureError):
        decode_access_token(token)


def test_tampered_token_is_rejected():
    token = create_access_token("subject")
    header, payload, signature = token.split(".")
    tampered_payload = payload[:-1] + ("A" if payload[-1] != "A" else "B")

    with pytest.raises(InvalidTokenError):
        decode_access_token(f"{header}.{tampered_payload}.{signature}")


def test_invalid_signature_is_rejected():
    token = create_access_token("subject")
    header, payload, _ = token.split(".")
    invalid_signature = jwt.encode(
        jwt.decode(token, options={"verify_signature": False}),
        TEST_SIGNING_KEY,
        algorithm="HS256",
    ).split(".")[2]

    with pytest.raises(InvalidTokenError):
        decode_access_token(f"{header}.{payload}.{invalid_signature}")


def test_hs384_token_is_rejected_when_hs256_is_configured():
    token = create_access_token("subject")
    claims = jwt.decode(token, options={"verify_signature": False})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", InsecureKeyLengthWarning)
        hs384_token = jwt.encode(
            claims,
            get_settings().SECRET_KEY,
            algorithm="HS384",
        )

    with pytest.raises(InvalidTokenError):
        decode_access_token(hs384_token)


def test_none_algorithm_token_is_rejected():
    token = create_access_token("subject")
    claims = jwt.decode(token, options={"verify_signature": False})
    unsigned_token = jwt.encode(claims, key="", algorithm="none")

    with pytest.raises(InvalidTokenError):
        decode_access_token(unsigned_token)


@pytest.mark.parametrize(
    "claims",
    [
        {"iat": 1, "exp": 2},
        {"sub": "subject", "exp": 2},
        {"sub": "subject", "iat": 1},
        {"sub": "", "iat": 1, "exp": 2},
    ],
)
def test_missing_or_invalid_required_claims_are_rejected(claims):
    settings_token = jwt.encode(claims, TEST_SIGNING_KEY, algorithm="HS256")

    with pytest.raises(InvalidTokenError):
        decode_access_token(settings_token)


def test_malformed_token_is_rejected():
    with pytest.raises(InvalidTokenError):
        decode_access_token("not-a-jwt")
