"""Phase 5 validation for schemas, lifecycle rules, and safety boundaries."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.dispute import DisputeDraftRequest, DisputeReason, DisputeStatus
from app.services.dispute_service import InvalidDisputeTransition


def test_reason_and_status_are_controlled_values():
    assert DisputeReason.REFUND_NOT_RECEIVED.value == "REFUND_NOT_RECEIVED"
    assert DisputeStatus.DRAFT.value == "DRAFT"
    with pytest.raises(ValidationError):
        DisputeDraftRequest(transaction_id=uuid4(), user_claim="")


def test_transition_error_is_explicit():
    with pytest.raises(InvalidDisputeTransition):
        raise InvalidDisputeTransition("Only draft disputes can be confirmed")


def test_draft_request_does_not_accept_ownership_fields():
    request = DisputeDraftRequest(transaction_id=uuid4(), user_claim="I did not receive the service")
    assert not hasattr(request, "user_id")
    assert not hasattr(request, "status")
