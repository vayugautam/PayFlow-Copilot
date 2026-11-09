"""Authenticated conversation and assistant routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.chat import (
    ChatMessageRequest, ChatMessageResponse, Citation, ConversationCreate,
    ConversationResponse, MessageResponse, ToolExecutionSummary,
)
from app.services.assistant_service import run_assistant
from app.services.conversation_service import (
    create_conversation, get_conversation, list_conversations, list_messages,
)
from app.services.llm_service import LLMError
from app.core.config import get_settings
from app.core.observability import authenticated_rate_limit_dependency

settings = get_settings()

router = APIRouter()


def _conversation_response(item) -> ConversationResponse:
    return ConversationResponse.model_validate(item, from_attributes=True)


def _message_response(item) -> MessageResponse:
    return MessageResponse.model_validate(item, from_attributes=True)


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(authenticated_rate_limit_dependency("conversation_create", settings.CHAT_RATE_LIMIT, settings.RATE_LIMIT_WINDOW_SECONDS))],
)
async def create(
    payload: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await create_conversation(db, current_user, payload.title)


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_conversations(db, current_user)


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def detail(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversation = await get_conversation(db, current_user, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def messages(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversation = await get_conversation(db, current_user, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return await list_messages(db, conversation.id)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ChatMessageResponse,
    dependencies=[Depends(authenticated_rate_limit_dependency("chat_message", settings.CHAT_RATE_LIMIT, settings.RATE_LIMIT_WINDOW_SECONDS))],
)
async def send_message(
    conversation_id: UUID,
    payload: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversation = await get_conversation(db, current_user, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    try:
        result = await run_assistant(db, current_user, conversation, payload.content)
    except LLMError as exc:
        await db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        await db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ChatMessageResponse(
        conversation_id=conversation.id,
        user_message=_message_response(result.user_message),
        assistant_message=_message_response(result.assistant_message),
        citations=[Citation(**item) for item in result.citations],
        tool_executions=[ToolExecutionSummary(**item) for item in result.tool_executions],
        created_at=result.assistant_message.created_at,
    )
