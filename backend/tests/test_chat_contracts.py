"""Focused Phase 4 contract tests that do not call Groq or external services."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.services.assistant_prompt import SYSTEM_PROMPT
from app.schemas.transaction import RetryEligibility
from app.services import assistant_service
from app.services.assistant_service import (
    _conversation_title,
    _grounding_context,
    _render_transaction_grounding,
)
from app.core.config import Settings
from app.services.chat_tools import (
    ListTransactionsArgs,
    TOOLS,
    execute_tool,
    tool_schemas,
)


def test_tool_registry_exposes_typed_schemas_without_user_id():
    names = {item["function"]["name"] for item in tool_schemas()}
    assert names == {
        "get_transaction",
        "list_transactions",
        "analyze_transaction_failure",
        "retrieve_payment_policy",
    }
    assert all("user_id" not in json.dumps(item) for item in tool_schemas())


def test_tool_arguments_are_bounded_and_validated():
    assert ListTransactionsArgs(limit=50, status="failed").limit == 50
    with pytest.raises(ValidationError):
        ListTransactionsArgs(limit=51)
    with pytest.raises(ValidationError):
        ListTransactionsArgs(limit=1, status="unknown")


@pytest.mark.asyncio
async def test_unknown_and_malformed_tool_calls_are_safe():
    ok, result = await execute_tool("not_registered", "{}", object(), object())
    assert not ok
    assert result == {"error": "Unknown tool"}

    ok, result = await execute_tool("get_transaction", '{"transaction_id":"bad"}', object(), object())
    assert not ok
    assert result["error"] == "Invalid arguments for get_transaction"


def test_system_prompt_contains_grounding_and_scope_boundaries():
    assert "Never invent transaction IDs" in SYSTEM_PROMPT
    assert "Never claim a refund has been issued" in SYSTEM_PROMPT
    assert "another user's information" in SYSTEM_PROMPT
    assert "always call analyze_transaction_failure" in SYSTEM_PROMPT
    assert "Do not interpret raw failure codes yourself" in SYSTEM_PROMPT


def test_legacy_groq_model_setting_is_used_when_llm_model_is_unset():
    settings = Settings(LLM_MODEL="", GROQ_MODEL="llama-3.3-70b-versatile")
    assert settings.llm_model == "llama-3.3-70b-versatile"


def test_conversation_title_is_compact_and_whitespace_normalized():
    assert _conversation_title("  Explain\nmy payment   ") == "Explain my payment"
    assert _conversation_title("x" * 100).endswith("…")
    assert len(_conversation_title("x" * 100)) == 72


def _analysis_payload(*, status="failed", failure_code="TIMEOUT"):
    return {
        "transaction_id": str(uuid4()),
        "transaction_status": status,
        "failure_code": failure_code,
        "category": "network" if status == "failed" else "payment_status",
        "title": "Payment processing timed out" if status == "failed" else "Payment is processing",
        "explanation": (
            "The payment result was not received within the expected processing time."
            if status == "failed"
            else "The payment is still being processed."
        ),
        "recommended_actions": ["Verify the transaction status before trying again."]
        if status == "failed"
        else ["Check the transaction status again later."],
        "retry_eligibility": "verify_status_first",
        "severity": "high" if status == "failed" else "medium",
    }


def test_grounding_context_is_a_validated_contract():
    context = _grounding_context({"found": True, "analysis": _analysis_payload()})

    assert context is not None
    assert context.retry_eligibility == RetryEligibility.VERIFY_STATUS_FIRST
    assert context.support_status == "supported"
    assert context.severity.value == "high"


def test_missing_transaction_has_no_grounding_context():
    assert _grounding_context({"found": False, "transaction_id": str(uuid4())}) is None


@pytest.mark.parametrize(
    ("status", "failure_code", "forbidden"),
    [
        ("successful", None, ("payment was refunded", "payment was settled")),
        ("pending", None, ("payment was refunded", "payment was settled")),
        (
            "failed",
            "TIMEOUT",
            ("payment was refunded", "payment was settled", "insufficient funds"),
        ),
    ],
)
def test_rendered_transaction_facts_do_not_invent_sensitive_outcomes(
    status, failure_code, forbidden
):
    payload = _analysis_payload(status=status, failure_code=failure_code)
    if status == "successful":
        payload.update(
            title="Payment completed",
            explanation="The payment completed successfully.",
            recommended_actions=["No further payment action is required."],
            retry_eligibility="do_not_retry",
            severity="low",
        )
    context = _grounding_context({"found": True, "analysis": payload})

    rendered = _render_transaction_grounding(context)

    assert all(term not in rendered.lower() for term in forbidden)
    assert "bank-settlement evidence" in rendered


@pytest.mark.asyncio
async def test_analyze_tool_call_returns_deterministic_answer(monkeypatch):
    transaction_id = str(uuid4())
    payload = _analysis_payload()
    payload["transaction_id"] = transaction_id
    tool_call = {
        "id": "tool-1",
        "function": {
            "name": "analyze_transaction_failure",
            "arguments": json.dumps({"transaction_id": transaction_id}),
        },
    }

    class FakeClient:
        async def complete(self, messages, tools):
            return SimpleNamespace(
                content="The payment was refunded and settled.",
                tool_calls=[tool_call],
                raw_messages=[{"role": "assistant", "content": ""}],
            )

    messages = []

    async def fake_add_message(db, conversation, *, role, content, **kwargs):
        message = SimpleNamespace(
            role=role,
            content=content,
            id=uuid4(),
            created_at=datetime.now(timezone.utc),
        )
        messages.append(message)
        return message

    async def fake_list_messages(db, conversation_id):
        return messages

    async def fake_execute_tool(name, raw_arguments, db, user):
        return True, {"found": True, "analysis": payload}

    class FakeDB:
        async def commit(self):
            return None

    monkeypatch.setattr(assistant_service, "GroqLLMClient", FakeClient)
    monkeypatch.setattr(assistant_service, "add_message", fake_add_message)
    monkeypatch.setattr(assistant_service, "list_messages", fake_list_messages)
    monkeypatch.setattr(assistant_service, "execute_tool", fake_execute_tool)

    result = await assistant_service.run_assistant(
        FakeDB(),
        SimpleNamespace(id=uuid4()),
        SimpleNamespace(id=uuid4(), title=None),
        "Why did this payment fail?",
    )

    assert "Payment processing timed out" in result.assistant_message.content
    assert "payment was refunded" not in result.assistant_message.content.lower()
    assert "payment was settled" not in result.assistant_message.content.lower()
    assert result.tool_executions == [
        {"tool_name": "analyze_transaction_failure", "success": True}
    ]
