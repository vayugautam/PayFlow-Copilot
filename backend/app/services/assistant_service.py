"""Groq tool-calling orchestration for authenticated conversations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, User
from app.schemas.assistant import TransactionGroundingContext
from app.schemas.transaction import TransactionAnalysisResponse
from app.services.assistant_prompt import SYSTEM_PROMPT
from app.services.chat_tools import execute_tool, tool_schemas
from app.services.conversation_service import add_message, list_messages
from app.services.llm_service import GroqLLMClient

MAX_CONTEXT_MESSAGES = 30
MAX_TOOL_ROUNDS = 4
MAX_CONVERSATION_TITLE_LENGTH = 72


@dataclass(frozen=True)
class AssistantResult:
    user_message: Any
    assistant_message: Any
    citations: list[dict[str, Any]]
    tool_executions: list[dict[str, Any]]


def _citation_items(result: dict[str, Any]) -> list[dict[str, Any]]:
    citations = []
    for item in result.get("items", []):
        citations.append(
            {
                "document_id": item["document_id"],
                "document_title": item["document_title"],
                "page_number": item.get("page_number"),
                "chunk_index": item["chunk_index"],
                "relevant_excerpt": item["content"][:500],
            }
        )
    return citations


def _conversation_title(content: str) -> str:
    """Create a compact, stable title from the opening user message."""
    normalized = " ".join(content.split())
    if len(normalized) <= MAX_CONVERSATION_TITLE_LENGTH:
        return normalized
    return f"{normalized[:MAX_CONVERSATION_TITLE_LENGTH - 1].rstrip()}…"


def _render_transaction_grounding(context: TransactionGroundingContext) -> str:
    """Render sensitive payment facts without giving the LLM room to alter them."""
    facts = [
        "**Verified transaction analysis**",
        f"- Transaction ID: `{context.transaction_id}`",
        f"- Status: {context.transaction_status}",
        f"- Failure code: {context.failure_code or 'Not recorded'}",
        f"- Deterministic result: {context.reason_title}",
        f"- {context.explanation}",
        f"- Retry eligibility: {context.retry_eligibility.value.replace('_', ' ')}",
        f"- Analysis severity: {context.severity.value}",
    ]
    if context.support_status == "unknown_or_unsupported":
        facts.append(
            "- The simulated system does not have a more specific, supported reason for this result."
        )
    if context.recommended_actions:
        facts.extend(["", "**Recommended next steps**"])
        facts.extend(f"- {action}" for action in context.recommended_actions)
    facts.extend([
        "",
        "The backend does not include bank-settlement evidence, so I cannot confirm whether funds settled or were received.",
    ])
    return "\n".join(facts)


def _grounding_context(result: dict[str, Any]) -> TransactionGroundingContext | None:
    """Validate tool output before it becomes a user-visible assistant answer."""
    if not result.get("found"):
        return None
    analysis = TransactionAnalysisResponse.model_validate(result.get("analysis"))
    return TransactionGroundingContext.from_analysis(analysis)


async def run_assistant(
    db: AsyncSession, user: User, conversation: Conversation, content: str
) -> AssistantResult:
    if not conversation.title:
        conversation.title = _conversation_title(content)
    user_message = await add_message(db, conversation, role="user", content=content)
    history = await list_messages(db, conversation.id)
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for message in history[-MAX_CONTEXT_MESSAGES:]:
        if message.role in {"user", "assistant"}:
            messages.append({"role": message.role, "content": message.content})

    client = GroqLLMClient()
    citations: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for _ in range(MAX_TOOL_ROUNDS):
        completion = await client.complete(messages, tool_schemas())
        messages.extend(completion.raw_messages)
        if not completion.tool_calls:
            answer = completion.content.strip()
            if not answer:
                raise RuntimeError("The assistant returned an empty response")
            assistant_message = await add_message(
                db, conversation, role="assistant", content=answer,
                metadata={"citations": citations, "tool_executions": summaries},
            )
            await db.commit()
            return AssistantResult(user_message, assistant_message, citations, summaries)
        transaction_context: TransactionGroundingContext | None = None
        missing_transaction_id: str | None = None
        for call in completion.tool_calls:
            function = call["function"]
            name = function["name"]
            ok, result = await execute_tool(name, function["arguments"], db, user)
            summaries.append({"tool_name": name, "success": ok})
            if name == "retrieve_payment_policy" and ok:
                citations.extend(_citation_items(result))
            if name == "analyze_transaction_failure" and ok:
                transaction_context = _grounding_context(result)
                if transaction_context is None:
                    missing_transaction_id = str(result.get("transaction_id") or "the requested transaction")
            serialized = json.dumps(result, default=str)
            messages.append(
                {"role": "tool", "tool_call_id": call["id"], "name": name, "content": serialized}
            )
            await add_message(
                db, conversation, role="tool", content=serialized,
                tool_name=name, tool_call_id=call["id"], metadata={"success": ok},
            )
        if transaction_context is not None:
            assistant_message = await add_message(
                db,
                conversation,
                role="assistant",
                content=_render_transaction_grounding(transaction_context),
                metadata={"citations": citations, "tool_executions": summaries, "grounded_transaction": transaction_context.model_dump(mode="json")},
            )
            await db.commit()
            return AssistantResult(user_message, assistant_message, citations, summaries)
        if missing_transaction_id is not None:
            assistant_message = await add_message(
                db,
                conversation,
                role="assistant",
                content=f"I could not find transaction `{missing_transaction_id}` in your account, so I cannot analyze it.",
                metadata={"citations": citations, "tool_executions": summaries},
            )
            await db.commit()
            return AssistantResult(user_message, assistant_message, citations, summaries)
    raise RuntimeError("The assistant exceeded the maximum tool-call rounds")
