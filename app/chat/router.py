"""
Chat API router — REST + SSE endpoints for AI chat.

Endpoints:
    GET    /api/chat/conversations           — list user's conversations
    POST   /api/chat/conversations           — create conversation
    GET    /api/chat/conversations/{id}      — get conversation
    PATCH  /api/chat/conversations/{id}      — update (title/archive)
    DELETE /api/chat/conversations/{id}      — archive conversation
    GET    /api/chat/conversations/{id}/messages — get message history
    POST   /api/chat/send                     — non-streaming send
    GET    /api/chat/stream/{conv_id}         — SSE streaming chat
    GET    /api/chat/tools                    — list available tools

All endpoints require JWT authentication via get_current_user.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.chat.schemas import (
    ChatRequest,
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    MessageResponse,
)
from app.chat.service import get_chat_service
from app.chat.tool_registry import tool_registry
from app.chat.sse import chat_event_generator
from app.routers.auth_db import get_current_user

logger = logging.getLogger("webapi.chat")

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ── Conversations ──────────────────────────────────────────────

@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    archived: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """List the current user's conversations."""
    svc = get_chat_service()
    return await svc.list_conversations(user["id"], archived=archived, limit=limit)


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    data: ConversationCreate,
    user: dict = Depends(get_current_user),
):
    """Create a new conversation."""
    svc = get_chat_service()
    conv = await svc.create_conversation(user["id"], data)
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        model_provider=conv.model_provider,
        model_name=conv.model_name,
        message_count=conv.message_count,
        created_at=conv.created_at.isoformat() if hasattr(conv.created_at, "isoformat") else str(conv.created_at),
        updated_at=conv.updated_at.isoformat() if hasattr(conv.updated_at, "isoformat") else str(conv.updated_at),
        is_archived=conv.is_archived,
    )


@router.get("/conversations/{conv_id}", response_model=ConversationResponse)
async def get_conversation(
    conv_id: str,
    user: dict = Depends(get_current_user),
):
    """Get a single conversation by ID."""
    svc = get_chat_service()
    conv = await svc.get_conversation(user["id"], conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        model_provider=conv.model_provider,
        model_name=conv.model_name,
        message_count=conv.message_count,
        created_at=conv.created_at.isoformat() if hasattr(conv.created_at, "isoformat") else str(conv.created_at),
        updated_at=conv.updated_at.isoformat() if hasattr(conv.updated_at, "isoformat") else str(conv.updated_at),
        is_archived=conv.is_archived,
    )


@router.patch("/conversations/{conv_id}")
async def update_conversation(
    conv_id: str,
    data: ConversationUpdate,
    user: dict = Depends(get_current_user),
):
    """Update conversation title or archive status."""
    svc = get_chat_service()
    ok = await svc.update_conversation(
        user["id"], conv_id,
        title=data.title,
        is_archived=data.is_archived,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "ok"}


@router.delete("/conversations/{conv_id}")
async def delete_conversation(
    conv_id: str,
    user: dict = Depends(get_current_user),
):
    """Soft-delete (archive) a conversation."""
    svc = get_chat_service()
    ok = await svc.delete_conversation(user["id"], conv_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "ok"}


# ── Messages ──────────────────────────────────────────────────

@router.get("/conversations/{conv_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    conv_id: str,
    limit: int = Query(50, ge=1, le=500),
    user: dict = Depends(get_current_user),
):
    """Get message history for a conversation."""
    svc = get_chat_service()
    conv = await svc.get_conversation(user["id"], conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return await svc.get_messages(user["id"], conv_id, limit=limit)


@router.post("/send", response_model=MessageResponse)
async def send_message(
    data: ChatRequest,
    user: dict = Depends(get_current_user),
):
    """Send a message (non-streaming). Returns the full assistant response."""
    svc = get_chat_service()
    conv = await svc.get_conversation(user["id"], data.conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return await svc.send_message(user["id"], data)


# ── Streaming ─────────────────────────────────────────────────

@router.get("/stream/{conv_id}")
async def stream_chat(
    conv_id: str,
    message: str = Query(..., min_length=1),
    user: dict = Depends(get_current_user),
):
    """SSE streaming chat endpoint."""
    svc = get_chat_service()
    conv = await svc.get_conversation(user["id"], conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return StreamingResponse(
        chat_event_generator(
            conversation_id=conv_id,
            user_id=user["id"],
            message=message,
            chat_service=svc,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Tools ─────────────────────────────────────────────────────

@router.get("/tools")
async def list_tools(user: dict = Depends(get_current_user)):
    """List available chat tools."""
    return tool_registry.list_tools()
