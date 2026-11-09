"""Draft, lifecycle, and ownership operations for disputes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Dispute, User
from app.schemas.dispute import (
    DisputeReason,
    DisputeStatus,
    EvidenceReference,
    EvidenceSupport,
    StructuredDisputeDraft,
)
from app.services.audit_service import record_event
from app.services.knowledge_service import retrieve
from app.services.llm_service import GroqLLMClient
from app.services.payment_intelligence import analyze_transaction
from app.services.transaction_service import get_transaction_by_id


class DisputeError(ValueError):
    pass


class DisputeNotFound(DisputeError):
    pass


class InvalidDisputeTransition(DisputeError):
    pass


def _parse_structured_draft(
    generated: dict,
    *,
    user_claim: str,
    transaction: object,
    policy_items: list[dict],
) -> StructuredDisputeDraft:
    """Validate model output while deriving sensitive facts from backend data."""
    reason = DisputeReason(generated["reason"]).value
    title = str(generated["title"]).strip()
    description = str(generated["description"]).strip()
    checklist = generated.get("evidence_checklist")
    if not title or not description or not isinstance(checklist, list):
        raise ValueError("Missing required draft fields")

    allowed_refs = {
        (
            str(item["document_id"]),
            int(item["chunk_index"]),
        ): EvidenceReference(
            document_id=item["document_id"],
            document_title=item["document_title"],
            page_number=item.get("page_number"),
            chunk_index=int(item["chunk_index"]),
        )
        for item in policy_items
    }
    raw_refs = generated.get("evidence_references", [])
    if not isinstance(raw_refs, list):
        raise ValueError("Evidence references must be a list")
    references = []
    for raw_ref in raw_refs:
        ref = EvidenceReference.model_validate(raw_ref)
        key = (str(ref.document_id), ref.chunk_index)
        if key not in allowed_refs:
            raise ValueError("Draft cited evidence that was not retrieved")
        references.append(allowed_refs[key])

    try:
        support = EvidenceSupport(generated.get("evidence_support", EvidenceSupport.INSUFFICIENT_EVIDENCE))
    except ValueError as exc:
        raise ValueError("Unsupported evidence classification") from exc
    if not policy_items:
        support = EvidenceSupport.INSUFFICIENT_EVIDENCE
        references = []
    elif support == EvidenceSupport.SUPPORTED and not references:
        raise ValueError("Supported evidence requires retrieved references")

    return StructuredDisputeDraft(
        title=title[:255],
        user_claim=user_claim,
        transaction_facts={
            "transaction_id": str(transaction.id),
            "amount": str(transaction.amount),
            "currency": transaction.currency,
            "status": transaction.status,
            "merchant": transaction.merchant,
            "failure_code": transaction.failure_code or "not recorded",
        },
        supporting_policy_evidence=[
            str(item) for item in generated.get("supporting_policy_evidence", [])
        ][:20],
        evidence_references=references,
        evidence_support=support,
        missing_information=[
            str(item) for item in generated.get("missing_information", [])
        ][:20],
        user_review_required=True,
    )


async def get_owned_dispute(db: AsyncSession, user: User, dispute_id: UUID) -> Dispute | None:
    return await db.scalar(select(Dispute).where(Dispute.id == dispute_id, Dispute.user_id == user.id))


async def create_draft(db: AsyncSession, user: User, transaction_id: UUID, user_claim: str,
                       conversation_id: UUID | None = None) -> Dispute:
    transaction = await get_transaction_by_id(db, user, transaction_id)
    if transaction is None:
        raise DisputeNotFound("Transaction not found")
    if conversation_id is not None:
        conversation = await db.scalar(select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id))
        if conversation is None:
            raise DisputeError("Conversation not found")
    policy_items = await retrieve(db, user, user_claim, 5)
    analysis = analyze_transaction(transaction)
    facts = {
        "transaction_id": str(transaction.id), "amount": str(transaction.amount),
        "currency": transaction.currency, "status": transaction.status,
        "merchant": transaction.merchant, "failure_code": transaction.failure_code,
        "occurred_at": transaction.occurred_at.isoformat(),
        "analysis": analysis.model_dump(mode="json"),
        "policy": [{"document_id": str(item["document_id"]), "document_title": item["document_title"],
                    "page_number": item.get("page_number"), "chunk_index": item["chunk_index"],
                    "content": item["content"][:1000]} for item in policy_items],
        "user_claim": user_claim,
    }
    prompt = (
        "Prepare a dispute draft from the verified JSON facts below. Return JSON with keys "
        "title, reason (one allowed value), description, evidence_checklist, "
        "supporting_policy_evidence, evidence_references, evidence_support, and "
        "missing_information. Evidence references must use only retrieved document_id and "
        "chunk_index pairs. Use evidence_support SUPPORTED, PARTIALLY_SUPPORTED, or "
        "INSUFFICIENT_EVIDENCE. Label the user's claim as unverified and never invent facts "
        "or citations. Allowed reasons: "
        f"{[reason.value for reason in DisputeReason]}. Facts: {json.dumps(facts, default=str)}"
    )
    completion = await GroqLLMClient().complete(
        [{"role": "system", "content": "You prepare factual drafts requiring user review."},
         {"role": "user", "content": prompt}], []
    )
    try:
        generated = json.loads(completion.content)
        structured = _parse_structured_draft(
            generated,
            user_claim=user_claim,
            transaction=transaction,
            policy_items=policy_items,
        )
        reason = DisputeReason(generated["reason"]).value
        title = structured.title
        description = str(generated["description"]).strip()
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise DisputeError("The dispute draft response was invalid") from exc
    evidence = {
        **structured.model_dump(mode="json"),
        "checklist": [str(item) for item in generated["evidence_checklist"][:20]],
        "policy_citations": [reference.model_dump(mode="json") for reference in structured.evidence_references],
    }
    dispute = Dispute(user_id=user.id, transaction_id=transaction.id, conversation_id=conversation_id,
                      title=title, description=description, reason=reason,
                      status=DisputeStatus.DRAFT.value, evidence=evidence)
    db.add(dispute)
    await db.flush()
    await record_event(db, user, action="DISPUTE_DRAFT_CREATED", entity_type="dispute",
                       entity_id=dispute.id, details={"transaction_id": str(transaction.id), "status": dispute.status})
    await db.commit()
    await db.refresh(dispute)
    return dispute


async def list_owned_disputes(db: AsyncSession, user: User, page: int, page_size: int) -> tuple[list[Dispute], int]:
    filters = [Dispute.user_id == user.id]
    total = int(await db.scalar(select(func.count()).select_from(Dispute).where(*filters)) or 0)
    result = await db.scalars(select(Dispute).where(*filters).order_by(
        Dispute.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    return list(result), total


async def update_draft(db: AsyncSession, user: User, dispute: Dispute, values: dict) -> Dispute:
    if dispute.status != DisputeStatus.DRAFT.value:
        raise InvalidDisputeTransition("Only draft disputes can be edited")
    for key, value in values.items():
        if value is not None:
            setattr(dispute, key, value.value if isinstance(value, DisputeReason) else value)
    await record_event(db, user, action="DISPUTE_DRAFT_MODIFIED", entity_type="dispute",
                       entity_id=dispute.id, details={"fields": list(values)})
    await db.commit()
    await db.refresh(dispute)
    return dispute


async def confirm_dispute(db: AsyncSession, user: User, dispute: Dispute) -> Dispute:
    if dispute.status != DisputeStatus.DRAFT.value:
        raise InvalidDisputeTransition("Only draft disputes can be confirmed")
    dispute.status = DisputeStatus.SUBMITTED.value
    dispute.confirmed_at = datetime.now(timezone.utc)
    await record_event(db, user, action="DISPUTE_CONFIRMED", entity_type="dispute",
                       entity_id=dispute.id, details={"status": dispute.status})
    await record_event(db, user, action="DISPUTE_STATUS_CHANGED", entity_type="dispute",
                       entity_id=dispute.id, details={"from": DisputeStatus.DRAFT.value, "to": dispute.status})
    await db.commit()
    await db.refresh(dispute)
    return dispute


async def cancel_dispute(db: AsyncSession, user: User, dispute: Dispute) -> Dispute:
    if dispute.status not in {DisputeStatus.DRAFT.value, DisputeStatus.SUBMITTED.value}:
        raise InvalidDisputeTransition("This dispute cannot be cancelled")
    previous = dispute.status
    dispute.status = DisputeStatus.CANCELLED.value
    await record_event(db, user, action="DISPUTE_CANCELLED", entity_type="dispute",
                       entity_id=dispute.id, details={"from": previous, "to": dispute.status})
    await record_event(db, user, action="DISPUTE_STATUS_CHANGED", entity_type="dispute",
                       entity_id=dispute.id, details={"from": previous, "to": dispute.status})
    await db.commit()
    await db.refresh(dispute)
    return dispute
