"""Chat API request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ConversationResponse(BaseModel):
    id: UUID
    title: str | None
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    tool_name: str | None = None
    created_at: datetime


class ChatMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=12000)


class Citation(BaseModel):
    document_id: UUID
    document_title: str
    page_number: int | None = None
    chunk_index: int
    relevant_excerpt: str


class ToolExecutionSummary(BaseModel):
    tool_name: str
    success: bool


class ChatMessageResponse(BaseModel):
    conversation_id: UUID
    user_message: MessageResponse
    assistant_message: MessageResponse
    citations: list[Citation] = []
    tool_executions: list[ToolExecutionSummary] = []
    created_at: datetime
