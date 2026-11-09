"""Internal contracts for deterministic, transaction-grounded assistant answers."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.transaction import (
    AnalysisSeverity,
    RetryEligibility,
    TransactionAnalysisResponse,
)


class TransactionGroundingContext(BaseModel):
    """Verified payment facts that may be rendered without LLM interpretation."""

    transaction_id: UUID
    transaction_status: Literal["successful", "failed", "pending", "refunded"]
    failure_code: str | None = None
    reason_title: str
    explanation: str
    recommended_actions: list[str] = Field(default_factory=list)
    retry_eligibility: RetryEligibility
    severity: AnalysisSeverity
    support_status: Literal["supported", "unknown_or_unsupported"]

    @classmethod
    def from_analysis(cls, analysis: TransactionAnalysisResponse) -> "TransactionGroundingContext":
        return cls(
            transaction_id=analysis.transaction_id,
            transaction_status=analysis.transaction_status,
            failure_code=analysis.failure_code,
            reason_title=analysis.title,
            explanation=analysis.explanation,
            recommended_actions=analysis.recommended_actions,
            retry_eligibility=analysis.retry_eligibility,
            severity=analysis.severity,
            support_status="unknown_or_unsupported" if analysis.category == "unknown" else "supported",
        )
