"""Validated server-side tools exposed to the LLM."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.transaction import TRANSACTION_STATUSES
from app.services.knowledge_service import retrieve
from app.services.payment_intelligence import analyze_transaction
from app.services.transaction_service import get_transaction_by_id, get_user_transactions


class ToolInputError(ValueError):
    pass


class GetTransactionArgs(BaseModel):
    transaction_id: UUID


class ListTransactionsArgs(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)
    status: str | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.status is not None and self.status not in TRANSACTION_STATUSES:
            raise ValueError("Unsupported transaction status")


class AnalyzeTransactionArgs(BaseModel):
    transaction_id: UUID


class RetrievePolicyArgs(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    document_id: UUID | None = None


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    arguments: type[BaseModel]
    execute: Callable[[AsyncSession, User, BaseModel], Awaitable[dict[str, Any]]]

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.arguments.model_json_schema(),
            },
        }


def _transaction_result(transaction: Any) -> dict[str, Any]:
    return {
        "transaction_id": str(transaction.id),
        "amount": str(transaction.amount),
        "currency": transaction.currency,
        "status": transaction.status,
        "merchant": transaction.merchant,
        "payment_method": transaction.payment_method,
        "failure_code": transaction.failure_code,
        "occurred_at": transaction.occurred_at.isoformat(),
    }


async def _get_transaction(db: AsyncSession, user: User, args: GetTransactionArgs) -> dict[str, Any]:
    transaction = await get_transaction_by_id(db, user, args.transaction_id)
    return {"found": transaction is not None, "transaction": _transaction_result(transaction) if transaction else None}


async def _list_transactions(db: AsyncSession, user: User, args: ListTransactionsArgs) -> dict[str, Any]:
    transactions, total = await get_user_transactions(
        db, user, page=1, page_size=args.limit, status=args.status
    )
    return {"total": total, "transactions": [_transaction_result(item) for item in transactions]}


async def _analyze_transaction(db: AsyncSession, user: User, args: AnalyzeTransactionArgs) -> dict[str, Any]:
    transaction = await get_transaction_by_id(db, user, args.transaction_id)
    if transaction is None:
        return {"found": False, "transaction_id": str(args.transaction_id), "analysis": None}
    return {"found": True, "analysis": analyze_transaction(transaction).model_dump(mode="json")}


async def _retrieve_policy(db: AsyncSession, user: User, args: RetrievePolicyArgs) -> dict[str, Any]:
    items = await retrieve(db, user, args.query, 5, args.document_id)
    return {
        "items": [
            {
                "document_id": str(item["document_id"]),
                "document_title": item["document_title"],
                "page_number": item.get("page_number"),
                "chunk_index": item["chunk_index"],
                "score": item["score"],
                "content": item["content"],
            }
            for item in items
        ]
    }


TOOLS = {
    "get_transaction": ToolDefinition(
        "get_transaction", "Get one transaction owned by the authenticated user.", GetTransactionArgs, _get_transaction
    ),
    "list_transactions": ToolDefinition(
        "list_transactions", "List concise transactions owned by the authenticated user.", ListTransactionsArgs, _list_transactions
    ),
    "analyze_transaction_failure": ToolDefinition(
        "analyze_transaction_failure", "Run deterministic backend analysis for an owned transaction.", AnalyzeTransactionArgs, _analyze_transaction
    ),
    "retrieve_payment_policy": ToolDefinition(
        "retrieve_payment_policy", "Retrieve owned payment policy chunks and source metadata.", RetrievePolicyArgs, _retrieve_policy
    ),
}


def tool_schemas() -> list[dict[str, Any]]:
    return [definition.schema() for definition in TOOLS.values()]


async def execute_tool(
    name: str, raw_arguments: str, db: AsyncSession, user: User
) -> tuple[bool, dict[str, Any]]:
    definition = TOOLS.get(name)
    if definition is None:
        return False, {"error": "Unknown tool"}
    try:
        arguments = definition.arguments.model_validate_json(raw_arguments)
        return True, await definition.execute(db, user, arguments)
    except (ValidationError, json.JSONDecodeError, ValueError) as exc:
        return False, {"error": f"Invalid arguments for {name}"}
    except Exception:
        return False, {"error": f"Tool {name} failed"}
