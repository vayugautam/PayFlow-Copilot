"""Transaction API schemas."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

TRANSACTION_STATUSES = {"successful", "failed", "pending", "refunded"}


class AnalysisCategory(StrEnum):
    FUNDS = "funds"
    AUTHORIZATION = "authorization"
    CARD = "card"
    NETWORK = "network"
    FRAUD = "fraud"
    LIMITS = "limits"
    ACCOUNT = "account"
    PROCESSOR = "processor"
    PAYMENT_STATUS = "payment_status"
    UNKNOWN = "unknown"


class RetryEligibility(StrEnum):
    RETRY_NOW = "retry_now"
    RETRY_AFTER_ACTION = "retry_after_action"
    VERIFY_STATUS_FIRST = "verify_status_first"
    DO_NOT_RETRY = "do_not_retry"
    UNKNOWN = "unknown"


class AnalysisSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TransactionCreate(BaseModel):
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=12)
    currency: str = Field(min_length=3, max_length=3)
    status: str
    merchant: str = Field(min_length=1, max_length=255)
    description: str | None = None
    failure_code: str | None = Field(default=None, max_length=100)
    payment_method: str | None = Field(default=None, max_length=50)
    occurred_at: datetime

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("Currency must be a three-letter code")
        return normalized

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in TRANSACTION_STATUSES:
            raise ValueError("Unsupported transaction status")
        return normalized

    @field_validator("merchant", mode="before")
    @classmethod
    def normalize_merchant(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Merchant must not be empty")
        return normalized

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    amount: Decimal
    currency: str
    status: str
    merchant: str
    description: str | None
    failure_code: str | None
    payment_method: str | None
    provider_order_id: str | None
    provider_payment_id: str | None
    failure_description: str | None
    failure_source: str | None
    failure_step: str | None
    failure_reason: str | None
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    total: int
    page: int
    page_size: int
    pages: int


class TransactionAnalysisResponse(BaseModel):
    transaction_id: UUID
    transaction_status: str
    failure_code: str | None
    category: AnalysisCategory
    title: str
    explanation: str
    recommended_actions: list[str]
    retry_eligibility: RetryEligibility
    severity: AnalysisSeverity
