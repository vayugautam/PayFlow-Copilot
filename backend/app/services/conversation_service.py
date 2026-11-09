"""Ownership-scoped conversation persistence operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message, User


async def create_conversation(db: AsyncSession, user: User, title: str | None = None) -> Conversation:
    # The original conversation migration created these columns without database
    # defaults. Populate them explicitly so a fresh conversation cannot fail with
    # a NOT NULL violation on installations already at that migration revision.
    now = datetime.now(timezone.utc)
    conversation = Conversation(
        user_id=user.id,
        title=title.strip() if title else None,
        created_at=now,
        updated_at=now,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def list_conversations(db: AsyncSession, user: User) -> list[Conversation]:
    result = await db.scalars(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
    )
    return list(result)


async def get_conversation(
    db: AsyncSession, user: User, conversation_id: UUID
) -> Conversation | None:
    return await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id
        )
    )


async def list_messages(db: AsyncSession, conversation_id: UUID) -> list[Message]:
    result = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
    )
    return list(result)


async def add_message(
    db: AsyncSession,
    conversation: Conversation,
    *,
    role: str,
    content: str,
    tool_name: str | None = None,
    tool_call_id: str | None = None,
    metadata: dict | None = None,
) -> Message:
    if role not in {"user", "assistant", "tool"}:
        raise ValueError("Unsupported message role")
    message = Message(
        conversation_id=conversation.id,
        role=role,
        content=content,
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        extra_metadata=metadata,
        created_at=datetime.now(timezone.utc),
    )
    db.add(message)
    conversation.updated_at = message.created_at
    await db.flush()
    await db.refresh(message)
    return message
