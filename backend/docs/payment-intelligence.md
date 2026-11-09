# Deterministic Payment Intelligence

The payment intelligence engine classifies simulated transaction outcomes using
a fixed, auditable mapping. It does not call an LLM, initiate payments, or
retry transactions.

## Supported failure codes

`INSUFFICIENT_FUNDS`, `DO_NOT_HONOR`, `EXPIRED_CARD`, `INVALID_CVV`,
`INCORRECT_PIN`, `NETWORK_ERROR`, `TIMEOUT`, `FRAUD_SUSPECTED`,
`LIMIT_EXCEEDED`, `CARD_BLOCKED`, `PROCESSOR_UNAVAILABLE`, `INVALID_ACCOUNT`,
and `TRANSACTION_NOT_PERMITTED`.

Unrecognized or missing codes use a safe `unknown` classification.

## Retry eligibility

- `retry_after_action`: resolve the stated balance, payment-method, limit,
  account, or processor issue first.
- `verify_status_first`: use for timeouts, network errors, and pending payments;
  do not retry while the outcome is uncertain.
- `do_not_retry`: use for fraud reviews, blocked methods, and completed or
  refunded payments.
- `unknown`: no automatic retry recommendation is made.

The codes and explanations represent this simulated system only. They do not
assert issuer-specific meanings or guarantee how a particular bank maps codes.
