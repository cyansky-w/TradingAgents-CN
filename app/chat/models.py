"""
MongoDB document models for chat conversations and messages.

Collections:
    conversations  - Conversation metadata (one per chat session)
    chat_messages  - Individual messages within a conversation
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class Conversation(BaseModel):
    """Conversation document stored in MongoDB 'conversations' collection."""

    id: str = Field(default_factory=new_id)
    user_id: str
    title: str = "New Chat"
    model_provider: str = ""
    model_name: str = ""
    system_prompt: str = ""
    message_count: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    is_archived: bool = False
    metadata: dict = Field(default_factory=dict)

    class Config:
        collection_name = "conversations"


class ChatMessage(BaseModel):
    """Message document stored in MongoDB 'chat_messages' collection."""

    id: str = Field(default_factory=new_id)
    conversation_id: str
    user_id: str
    role: str  # "user" | "assistant" | "system" | "tool"
    content: str
    tool_calls: list[dict] = Field(default_factory=list)
    tool_call_id: str = ""
    token_usage: Optional[dict] = None  # {"prompt": N, "completion": N, "total": N}
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict = Field(default_factory=dict)

    class Config:
        collection_name = "chat_messages"
