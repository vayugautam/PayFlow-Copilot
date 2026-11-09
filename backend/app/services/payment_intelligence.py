"""Deterministic explanations for simulated payment transaction outcomes."""

from dataclasses import dataclass

from app.models import Transaction
from app.schemas.transaction import (
    AnalysisCategory,
    AnalysisSeverity,
    RetryEligibility,
    TransactionAnalysisResponse,
)


@dataclass(frozen=True)
class FailureKnowledge:
    category: AnalysisCategory
    title: str
    explanation: str
    recommended_actions: tuple[str, ...]
    retry_eligibility: RetryEligibility
    severity: AnalysisSeverity


_FAILURE_KNOWLEDGE: dict[str, FailureKnowledge] = {
    "INSUFFICIENT_FUNDS": FailureKnowledge(
        AnalysisCategory.FUNDS,
        "Insufficient funds",
        "The payment was declined because the available balance was not sufficient for this transaction.",
        ("Confirm that sufficient funds are available.",),
        RetryEligibility.RETRY_AFTER_ACTION,
        AnalysisSeverity.MEDIUM,
    ),
    "DO_NOT_HONOR": FailureKnowledge(
        AnalysisCategory.AUTHORIZATION,
        "Payment not authorized",
        "The payment was declined by the payment authorization process.",
        ("Contact the payment provider for more information.",),
        RetryEligibility.DO_NOT_RETRY,
        AnalysisSeverity.MEDIUM,
    ),
    "EXPIRED_CARD": FailureKnowledge(
        AnalysisCategory.CARD,
        "Expired payment method",
        "The payment method used for this transaction is expired.",
        ("Update the payment method before trying again.",),
        RetryEligibility.RETRY_AFTER_ACTION,
        AnalysisSeverity.MEDIUM,
    ),
    "INVALID_CVV": FailureKnowledge(
        AnalysisCategory.CARD,
        "Invalid security code",
        "The security code provided for the payment method was not accepted.",
        ("Check the payment details before trying again.",),
        RetryEligibility.RETRY_AFTER_ACTION,
        AnalysisSeverity.MEDIUM,
    ),
    "INCORRECT_PIN": FailureKnowledge(
        AnalysisCategory.AUTHORIZATION,
        "Incorrect PIN",
        "The PIN provided for this payment was not accepted.",
        ("Verify the PIN and follow the payment provider's guidance.",),
        RetryEligibility.RETRY_AFTER_ACTION,
        AnalysisSeverity.MEDIUM,
    ),
    "NETWORK_ERROR": FailureKnowledge(
        AnalysisCategory.NETWORK,
        "Network error",
        "The payment could not be completed because a network error interrupted processing.",
        ("Confirm that no payment was completed before trying again.",),
        RetryEligibility.VERIFY_STATUS_FIRST,
        AnalysisSeverity.MEDIUM,
    ),
    "TIMEOUT": FailureKnowledge(
        AnalysisCategory.NETWORK,
        "Payment processing timed out",
        "The payment result was not received within the expected processing time.",
        ("Verify the transaction status before trying again.",),
        RetryEligibility.VERIFY_STATUS_FIRST,
        AnalysisSeverity.HIGH,
    ),
    "FRAUD_SUSPECTED": FailureKnowledge(
        AnalysisCategory.FRAUD,
        "Payment review required",
        "The payment was declined for a security review.",
        ("Contact the bank or payment provider before taking further action.",),
        RetryEligibility.DO_NOT_RETRY,
        AnalysisSeverity.HIGH,
    ),
    "LIMIT_EXCEEDED": FailureKnowledge(
        AnalysisCategory.LIMITS,
        "Transaction limit exceeded",
        "The payment exceeded an applicable transaction limit.",
        ("Check the applicable payment limits before trying again.",),
        RetryEligibility.RETRY_AFTER_ACTION,
        AnalysisSeverity.MEDIUM,
    ),
    "CARD_BLOCKED": FailureKnowledge(
        AnalysisCategory.CARD,
        "Payment method blocked",
        "The payment method could not be used because it is blocked.",
        ("Contact the bank or payment provider before trying again.",),
        RetryEligibility.DO_NOT_RETRY,
        AnalysisSeverity.HIGH,
    ),
    "PROCESSOR_UNAVAILABLE": FailureKnowledge(
        AnalysisCategory.PROCESSOR,
        "Payment processor unavailable",
        "The payment processor was unavailable while this payment was being processed.",
        ("Try again only after processor availability is restored.",),
        RetryEligibility.RETRY_AFTER_ACTION,
        AnalysisSeverity.HIGH,
    ),
    "INVALID_ACCOUNT": FailureKnowledge(
        AnalysisCategory.ACCOUNT,
        "Invalid account details",
        "The account details provided for this payment were not accepted.",
        ("Check the account details before trying again.",),
        RetryEligibility.RETRY_AFTER_ACTION,
        AnalysisSeverity.MEDIUM,
    ),
    "TRANSACTION_NOT_PERMITTED": FailureKnowledge(
        AnalysisCategory.AUTHORIZATION,
        "Transaction not permitted",
        "This payment type was not permitted for the transaction.",
        ("Use an eligible payment method or contact the payment provider.",),
        RetryEligibility.DO_NOT_RETRY,
        AnalysisSeverity.MEDIUM,
    ),
}

_UNKNOWN_KNOWLEDGE = FailureKnowledge(
    AnalysisCategory.UNKNOWN,
    "Payment could not be completed",
    "The payment failed for an unrecognized reason in the simulated system.",
    ("Contact the payment provider for more information.",),
    RetryEligibility.UNKNOWN,
    AnalysisSeverity.MEDIUM,
)

_FAILURE_KNOWLEDGE["UNKNOWN"] = _UNKNOWN_KNOWLEDGE
SUPPORTED_FAILURE_CODES = frozenset(_FAILURE_KNOWLEDGE)


def normalize_failure_code(failure_code: str | None) -> str | None:
    """Normalize application-defined codes without guessing processor semantics.

    Numeric processor codes are intentionally preserved as unknown values. Their
    meanings vary by network and are not mapped by this simulated engine.
    """
    if failure_code is None:
        return None
    normalized = failure_code.strip().upper()
    return normalized or None


def _result(
    transaction: Transaction,
    *,
    failure_code: str | None,
    knowledge: FailureKnowledge,
) -> TransactionAnalysisResponse:
    return TransactionAnalysisResponse(
        transaction_id=transaction.id,
        transaction_status=transaction.status,
        failure_code=failure_code,
        category=knowledge.category,
        title=knowledge.title,
        explanation=knowledge.explanation,
        recommended_actions=list(knowledge.recommended_actions),
        retry_eligibility=knowledge.retry_eligibility,
        severity=knowledge.severity,
    )


def analyze_transaction(transaction: Transaction) -> TransactionAnalysisResponse:
    """Classify a transaction without initiating or retrying any payment."""
    transaction_status = (transaction.status or "").lower()
    if transaction_status == "successful":
        return _result(
            transaction,
            failure_code=None,
            knowledge=FailureKnowledge(
                AnalysisCategory.PAYMENT_STATUS,
                "Payment completed",
                "The payment completed successfully.",
                ("No further payment action is required.",),
                RetryEligibility.DO_NOT_RETRY,
                AnalysisSeverity.LOW,
            ),
        )
    if transaction_status == "pending":
        return _result(
            transaction,
            failure_code=None,
            knowledge=FailureKnowledge(
                AnalysisCategory.PAYMENT_STATUS,
                "Payment is processing",
                "The payment is still being processed.",
                ("Check the transaction status again later.",),
                RetryEligibility.VERIFY_STATUS_FIRST,
                AnalysisSeverity.MEDIUM,
            ),
        )
    if transaction_status == "refunded":
        return _result(
            transaction,
            failure_code=None,
            knowledge=FailureKnowledge(
                AnalysisCategory.PAYMENT_STATUS,
                "Payment refunded",
                "The payment has been refunded.",
                ("No further payment action is required unless the refund is not received as expected.",),
                RetryEligibility.DO_NOT_RETRY,
                AnalysisSeverity.LOW,
            ),
        )
    if transaction_status == "failed":
        normalized_code = normalize_failure_code(transaction.failure_code)
        return _result(
            transaction,
            failure_code=normalized_code,
            knowledge=_FAILURE_KNOWLEDGE.get(normalized_code or "UNKNOWN", _UNKNOWN_KNOWLEDGE),
        )
    return _result(
        transaction,
        failure_code=transaction.failure_code,
        knowledge=FailureKnowledge(
            AnalysisCategory.UNKNOWN,
            "Payment status unavailable",
            "The transaction has an unsupported status in the simulated system.",
            ("Verify the transaction status before taking further action.",),
            RetryEligibility.UNKNOWN,
            AnalysisSeverity.MEDIUM,
        ),
    )
