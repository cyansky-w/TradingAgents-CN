"""
Pydantic request/response schemas for the chat API.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Conversation ──────────────────────────────────────────────

class ConversationCreate(BaseModel):
    title: str = "New Chat"
    model_provider: str = ""
    model_name: str = ""
    system_prompt: str = ""
    agent_id: Optional[str] = None


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    is_archived: Optional[bool] = None


class ConversationResponse(BaseModel):
    id: str
    title: str
    model_provider: str
    model_name: str
    message_count: int
    created_at: str
    updated_at: str
    is_archived: bool
    agent_id: Optional[str] = None


# ── Messages ──────────────────────────────────────────────────

class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    tool_calls: list[dict] = []
    created_at: str
    token_usage: Optional[dict] = None


class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    stream: bool = True


class ChatStreamEvent(BaseModel):
    event: str  # "token" | "tool_call" | "tool_result" | "done" | "error"
    data: dict[str, Any] = Field(default_factory=dict)


# ── Tools ─────────────────────────────────────────────────────

class ToolInfo(BaseModel):
    name: str
    description: str
    category: str = "general"
