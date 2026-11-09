"""Unit and API coverage for deterministic transaction analysis."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.routes.transactions import router
from app.db.session import get_db
from app.main import app
from app.models import Transaction, User
from app.schemas.transaction import RetryEligibility
from app.services.payment_intelligence import (
    SUPPORTED_FAILURE_CODES,
    analyze_transaction,
    normalize_failure_code,
)


def make_transaction(
    *,
    status: str = "failed",
    failure_code: str | None = "TIMEOUT",
    user_id=None,
) -> Transaction:
    now = datetime.now(timezone.utc)
    return Transaction(
        id=uuid4(),
        user_id=user_id or uuid4(),
        amount=Decimal("25.00"),
        currency="USD",
        status=status,
        merchant="Test Merchant",
        failure_code=failure_code,
        occurred_at=now,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.parametrize("failure_code", sorted(SUPPORTED_FAILURE_CODES))
def test_every_supported_failure_code_is_classified(failure_code):
    result = analyze_transaction(make_transaction(failure_code=failure_code))
    assert result.failure_code == failure_code
    if failure_code != "UNKNOWN":
        assert result.category != "unknown"
    assert result.title
    assert result.explanation
    assert result.recommended_actions
    assert result.retry_eligibility
    assert result.severity


@pytest.mark.parametrize(
    ("failure_code", "eligibility"),
    [
        ("INSUFFICIENT_FUNDS", RetryEligibility.RETRY_AFTER_ACTION),
        ("EXPIRED_CARD", RetryEligibility.RETRY_AFTER_ACTION),
        ("INVALID_CVV", RetryEligibility.RETRY_AFTER_ACTION),
        ("FRAUD_SUSPECTED", RetryEligibility.DO_NOT_RETRY),
        ("TIMEOUT", RetryEligibility.VERIFY_STATUS_FIRST),
        ("NETWORK_ERROR", RetryEligibility.VERIFY_STATUS_FIRST),
        ("PROCESSOR_UNAVAILABLE", RetryEligibility.RETRY_AFTER_ACTION),
        ("UNKNOWN", RetryEligibility.UNKNOWN),
    ],
)
def test_retry_rules_are_explicit(failure_code, eligibility):
    result = analyze_transaction(make_transaction(failure_code=failure_code))
    assert result.retry_eligibility == eligibility


def test_unknown_and_missing_failure_codes_are_safe():
    unknown = analyze_transaction(make_transaction(failure_code="NEW_CODE"))
    missing = analyze_transaction(make_transaction(failure_code=None))
    assert unknown.category == "unknown"
    assert unknown.retry_eligibility == RetryEligibility.UNKNOWN
    assert missing.failure_code is None
    assert missing.category == "unknown"
    assert "completed" not in missing.explanation.lower()


@pytest.mark.parametrize(
    ("raw_code", "normalized_code"),
    [
        (" insufficient_funds ", "INSUFFICIENT_FUNDS"),
        ("51", "51"),
        ("", None),
        (None, None),
    ],
)
def test_failure_code_normalization_does_not_guess_numeric_meanings(
    raw_code, normalized_code
):
    assert normalize_failure_code(raw_code) == normalized_code


def test_numeric_processor_code_is_explicitly_unsupported():
    result = analyze_transaction(make_transaction(failure_code="51"))

    assert result.failure_code == "51"
    assert result.category == "unknown"
    assert result.retry_eligibility == RetryEligibility.UNKNOWN
    assert "unrecognized reason" in result.explanation


@pytest.mark.parametrize(
    ("transaction_status", "expected_title", "eligibility"),
    [
        ("successful", "Payment completed", RetryEligibility.DO_NOT_RETRY),
        ("pending", "Payment is processing", RetryEligibility.VERIFY_STATUS_FIRST),
        ("refunded", "Payment refunded", RetryEligibility.DO_NOT_RETRY),
    ],
)
def test_non_failed_statuses_are_not_classified_as_failures(
    transaction_status, expected_title, eligibility
):
    result = analyze_transaction(
        make_transaction(status=transaction_status, failure_code="TIMEOUT")
    )
    assert result.title == expected_title
    assert result.retry_eligibility == eligibility
    assert result.failure_code is None


class AnalysisSession:
    def __init__(self, transaction: Transaction):
        self.transaction = transaction

    async def scalar(self, statement):
        params = statement.compile().params
        requested_id = next(
            (value for key, value in params.items() if "id" in key),
            None,
        )
        if (
            requested_id == self.transaction.id
            and self.transaction.user_id in {
                value for key, value in params.items() if "user_id" in key
            }
        ):
            return self.transaction
        return None


@pytest.fixture
def analysis_client():
    user = User(
        id=uuid4(),
        email="analysis@example.com",
        password_hash="hash",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    transaction = make_transaction(user_id=user.id)
    session = AnalysisSession(transaction)

    async def override_user():
        return user

    async def override_db():
        yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    yield TestClient(app), user, transaction
    app.dependency_overrides.clear()


def test_analysis_endpoint_returns_structured_owned_result(analysis_client):
    client, _, transaction = analysis_client
    response = client.get(
        f"/api/v1/transactions/{transaction.id}/analysis"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["transaction_id"] == str(transaction.id)
    assert body["failure_code"] == "TIMEOUT"
    assert body["retry_eligibility"] == "verify_status_first"


def test_analysis_endpoint_rejects_missing_transaction(analysis_client):
    client, _, _ = analysis_client
    response = client.get(f"/api/v1/transactions/{uuid4()}/analysis")
    assert response.status_code == 404


def test_analysis_endpoint_requires_authentication():
    app.dependency_overrides.clear()
    response = TestClient(app).get(f"/api/v1/transactions/{uuid4()}/analysis")
    assert response.status_code == 401
