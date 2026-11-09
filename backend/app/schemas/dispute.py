"""Dispute and audit API schemas."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DisputeReason(StrEnum):
    FRAUDULENT_TRANSACTION = "FRAUDULENT_TRANSACTION"
    DUPLICATE_CHARGE = "DUPLICATE_CHARGE"
    PRODUCT_NOT_RECEIVED = "PRODUCT_NOT_RECEIVED"
    SERVICE_NOT_PROVIDED = "SERVICE_NOT_PROVIDED"
    INCORRECT_AMOUNT = "INCORRECT_AMOUNT"
    REFUND_NOT_RECEIVED = "REFUND_NOT_RECEIVED"
    OTHER = "OTHER"


class DisputeStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class EvidenceSupport(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class EvidenceReference(BaseModel):
    document_id: UUID
    document_title: str
    page_number: int | None = None
    chunk_index: int


class StructuredDisputeDraft(BaseModel):
    """Validated draft facts; it never represents a final dispute outcome."""

    title: str = Field(min_length=1, max_length=255)
    user_claim: str = Field(min_length=1, max_length=4000)
    transaction_facts: dict[str, str]
    supporting_policy_evidence: list[str] = Field(default_factory=list)
    evidence_references: list[EvidenceReference] = Field(default_factory=list)
    evidence_support: EvidenceSupport
    missing_information: list[str] = Field(default_factory=list)
    user_review_required: bool = True


class DisputeDraftRequest(BaseModel):
    transaction_id: UUID
    user_claim: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None


class DisputeUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=12000)
    reason: DisputeReason | None = None
    evidence: dict | None = None


class DisputeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    transaction_id: UUID
    conversation_id: UUID | None
    title: str
    description: str
    reason: DisputeReason
    status: DisputeStatus
    evidence: dict | None
    resolution: str | None
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None
    resolved_at: datetime | None


class DisputePage(BaseModel):
    items: list[DisputeResponse]
    total: int
    page: int
    page_size: int


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    actor_user_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID
    details: dict | None
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
