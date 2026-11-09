from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.dispute import EvidenceSupport, StructuredDisputeDraft
from app.services.dispute_service import _parse_structured_draft


def _transaction():
    return SimpleNamespace(
        id=uuid4(),
        amount="25.00",
        currency="USD",
        status="failed",
        merchant="Example Shop",
        failure_code="TIMEOUT",
    )


def _generated(document_id, chunk_index=0):
    return {
        "title": "Payment issue",
        "reason": "OTHER",
        "description": "Please review this transaction.",
        "evidence_checklist": ["Confirm the transaction record"],
        "supporting_policy_evidence": ["The policy describes review steps."],
        "evidence_references": [
            {
                "document_id": str(document_id),
                "document_title": "Refund policy",
                "chunk_index": chunk_index,
            }
        ],
        "evidence_support": "SUPPORTED",
        "missing_information": ["Customer confirmation"],
    }


def test_structured_draft_uses_authoritative_transaction_facts():
    document_id = uuid4()
    draft = _parse_structured_draft(
        _generated(document_id),
        user_claim="I was charged incorrectly.",
        transaction=_transaction(),
        policy_items=[
            {
                "document_id": document_id,
                "document_title": "Refund policy",
                "chunk_index": 0,
                "page_number": 1,
            }
        ],
    )

    assert draft.evidence_support == EvidenceSupport.SUPPORTED
    assert draft.transaction_facts["failure_code"] == "TIMEOUT"
    assert draft.user_review_required is True


def test_invalid_citation_reference_is_rejected():
    with pytest.raises(ValueError, match="not retrieved"):
        _parse_structured_draft(
            _generated(uuid4()),
            user_claim="Claim",
            transaction=_transaction(),
            policy_items=[],
        )


def test_no_policy_evidence_is_classified_as_insufficient():
    generated = _generated(uuid4())
    generated["evidence_references"] = []
    draft = _parse_structured_draft(
        generated,
        user_claim="Claim",
        transaction=_transaction(),
        policy_items=[],
    )

    assert draft.evidence_support == EvidenceSupport.INSUFFICIENT_EVIDENCE
    assert draft.evidence_references == []


def test_supported_claim_without_retrieved_reference_is_rejected():
    generated = _generated(uuid4())
    generated["evidence_references"] = []
    with pytest.raises(ValueError, match="requires retrieved references"):
        _parse_structured_draft(
            generated,
            user_claim="Claim",
            transaction=_transaction(),
            policy_items=[
                {
                    "document_id": uuid4(),
                    "document_title": "Other policy",
                    "chunk_index": 1,
                    "page_number": None,
                }
            ],
        )


def test_structured_contract_requires_core_fields():
    with pytest.raises(ValidationError):
        StructuredDisputeDraft(
            title="",
            user_claim="Claim",
            transaction_facts={},
            evidence_support=EvidenceSupport.SUPPORTED,
        )
