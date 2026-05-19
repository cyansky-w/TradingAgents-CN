"""
Chat service — core orchestration for AI chat.

Handles conversation CRUD, message persistence, LLM invocation with streaming,
tool calling via LangChain agents, and memory management.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.chat.models import ChatMessage, Conversation, new_id, utc_now
from app.chat.schemas import (
    ChatRequest,
    ConversationCreate,
    ConversationResponse,
    MessageResponse,
)
from app.chat.memory_manager import MemoryManager
from app.chat.tool_registry import tool_registry
from app.chat.llm_factory import create_chat_llm, get_chat_llm_config
from app.core.config import settings
from app.core.database import get_mongo_db

logger = logging.getLogger("webapi.chat.service")

DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant for TradingAgents-CN, a stock analysis platform.
You help users with stock market questions, analysis tasks, and platform features.
Be concise, accurate, and professional. When you don't know something, say so clearly.

Current time: {current_time}
"""


class ChatService:
    """Core chat service with conversation management and LLM streaming."""

    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager

    @property
    def conversations_col(self):
        return get_mongo_db()["conversations"]

    @property
    def messages_col(self):
        return get_mongo_db()["chat_messages"]

    # ── Conversation CRUD ────────────────────────────────────

    async def create_conversation(
        self, user_id: str, data: ConversationCreate
    ) -> Conversation:
        conv = Conversation(
            user_id=user_id,
            title=data.title or "New Chat",
            model_provider=data.model_provider,
            model_name=data.model_name,
            system_prompt=data.system_prompt,
        )
        await self.conversations_col.insert_one(conv.model_dump())
        logger.info(f"Created conversation {conv.id} for user {user_id}")
        return conv

    async def list_conversations(
        self, user_id: str, archived: bool = False, limit: int = 50
    ) -> List[ConversationResponse]:
        cursor = self.conversations_col.find(
            {"user_id": user_id, "is_archived": archived}
        ).sort("updated_at", -1).limit(limit)

        results = []
        async for doc in cursor:
            results.append(ConversationResponse(
                id=doc["id"],
                title=doc.get("title", "New Chat"),
                model_provider=doc.get("model_provider", ""),
                model_name=doc.get("model_name", ""),
                message_count=doc.get("message_count", 0),
                created_at=_iso(doc.get("created_at")),
                updated_at=_iso(doc.get("updated_at")),
                is_archived=doc.get("is_archived", False),
            ))
        return results

    async def get_conversation(
        self, user_id: str, conv_id: str
    ) -> Optional[Conversation]:
        doc = await self.conversations_col.find_one(
            {"id": conv_id, "user_id": user_id}
        )
        if not doc:
            return None
        return Conversation(**doc)

    async def update_conversation(
        self, user_id: str, conv_id: str, title: str = None, is_archived: bool = None
    ) -> bool:
        update = {"updated_at": utc_now()}
        if title is not None:
            update["title"] = title
        if is_archived is not None:
            update["is_archived"] = is_archived

        result = await self.conversations_col.update_one(
            {"id": conv_id, "user_id": user_id}, {"$set": update}
        )
        return result.modified_count > 0

    async def delete_conversation(self, user_id: str, conv_id: str) -> bool:
        """Soft-delete: archive the conversation."""
        return await self.update_conversation(user_id, conv_id, is_archived=True)

    async def auto_title(self, user_id: str, conv_id: str, first_message: str) -> None:
        """Auto-generate conversation title from first message."""
        title = first_message.strip()[:50]
        if len(first_message) > 50:
            title += "..."
        await self.update_conversation(user_id, conv_id, title=title)

    # ── Messages ─────────────────────────────────────────────

    async def get_messages(
        self, user_id: str, conv_id: str, limit: int = 50
    ) -> List[MessageResponse]:
        cursor = self.messages_col.find(
            {"conversation_id": conv_id, "user_id": user_id}
        ).sort("created_at", 1).limit(limit)

        results = []
        async for doc in cursor:
            results.append(MessageResponse(
                id=doc["id"],
                conversation_id=doc["conversation_id"],
                role=doc.get("role", "user"),
                content=doc.get("content", ""),
                tool_calls=doc.get("tool_calls", []),
                created_at=_iso(doc.get("created_at")),
                token_usage=doc.get("token_usage"),
            ))
        return results

    async def save_message(self, msg: ChatMessage) -> None:
        await self.messages_col.insert_one(msg.model_dump())
        await self.conversations_col.update_one(
            {"id": msg.conversation_id},
            {
                "$inc": {"message_count": 1},
                "$set": {"updated_at": utc_now()},
            },
        )
        await self.memory.add_to_buffer(
            msg.user_id, msg.conversation_id, msg.model_dump()
        )

    # ── Chat Processing ───────────────────────────────────────

    async def send_message(
        self, user_id: str, data: ChatRequest
    ) -> MessageResponse:
        """Non-streaming message send. Returns full assistant response."""
        user_msg = ChatMessage(
            conversation_id=data.conversation_id,
            user_id=user_id,
            role="user",
            content=data.message,
        )
        await self.save_message(user_msg)

        # Build context
        buffer = await self.memory.get_buffer(user_id, data.conversation_id)
        langchain_messages = _build_langchain_messages(
            buffer, data.message, await self._get_system_prompt(data.conversation_id)
        )

        # Get LLM
        provider, model, api_key, base_url, _ = await get_chat_llm_config()
        llm = await create_chat_llm(provider, model, streaming=False)

        # Invoke
        from langchain_core.messages import HumanMessage, SystemMessage
        response = await llm.ainvoke([
            SystemMessage(content=langchain_messages[0].content),
            *[HumanMessage(content=m.content) if m.type == "human" else m
              for m in langchain_messages[1:]],
        ])

        assistant_msg = ChatMessage(
            conversation_id=data.conversation_id,
            user_id=user_id,
            role="assistant",
            content=response.content,
            token_usage=_extract_usage(response),
        )
        await self.save_message(assistant_msg)

        return MessageResponse(
            id=assistant_msg.id,
            conversation_id=assistant_msg.conversation_id,
            role="assistant",
            content=assistant_msg.content,
            created_at=_iso(assistant_msg.created_at),
            token_usage=assistant_msg.token_usage,
        )

    async def stream_response(
        self,
        user_id: str,
        conversation_id: str,
        message: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream the LLM response as an async generator of event dicts.

        Each yielded dict: {"event": "token"|"tool_call"|"done"|"error", "data": {...}}
        """
        try:
            # Save user message
            user_msg = ChatMessage(
                conversation_id=conversation_id,
                user_id=user_id,
                role="user",
                content=message,
            )
            await self.save_message(user_msg)

            # Auto-title if first message
            conv = await self.get_conversation(user_id, conversation_id)
            if conv and conv.message_count <= 2:
                await self.auto_title(user_id, conversation_id, message)

            # Build message context
            buffer = await self.memory.get_buffer(user_id, conversation_id)
            system_prompt = await self._get_system_prompt(conversation_id)

            # Recall long-term memory
            ltm_snippets = await self.memory.recall_long_term(user_id, message)
            if ltm_snippets:
                system_prompt += "\n\nRelevant context from previous conversations:\n"
                for snippet in ltm_snippets:
                    system_prompt += f"- {snippet}\n"

            langchain_messages = _build_langchain_messages(
                buffer, message, system_prompt
            )

            # Build tool list from registry
            tools = tool_registry.get_all() if not tool_registry.empty else None

            # Create streaming LLM. Disable thinking mode when tools are active
            # because LangChain drops reasoning_content from API responses, causing
            # DeepSeek to reject follow-up calls with "reasoning_content must be
            # passed back to the API" (400).
            llm = await create_chat_llm(
                streaming=True,
                temperature=0.7,
                max_tokens=4096,
                extra_body={"thinking": {"type": "disabled"}} if tools else None,
            )

            # Stream
            full_content = ""
            if tools:
                # Agent-based streaming (tools available)
                from langgraph.prebuilt import create_react_agent
                from langchain_core.messages import AIMessage, ToolMessage

                agent = create_react_agent(llm, tools)
                async for chunk in agent.astream(
                    {"messages": langchain_messages},
                    stream_mode="messages",
                ):
                    # stream_mode="messages" yields (ai_message_chunk, metadata) tuples
                    if not isinstance(chunk, tuple) or len(chunk) < 1:
                        continue

                    msg_chunk = chunk[0]

                    # Emit tool_call events for AIMessage chunks with tool_calls
                    if isinstance(msg_chunk, AIMessage) and getattr(msg_chunk, "tool_calls", None):
                        for tc in msg_chunk.tool_calls:
                            tc_name = tc.get("name", "")
                            if not tc_name:
                                continue
                            yield {
                                "event": "tool_call",
                                "data": {
                                    "name": tc_name,
                                    "args": tc.get("args", {}),
                                    "id": tc.get("id", ""),
                                },
                            }

                    # Emit tool_result events for ToolMessage
                    if isinstance(msg_chunk, ToolMessage):
                        tc_name = getattr(msg_chunk, "name", "")
                        tc_content = str(getattr(msg_chunk, "content", ""))
                        yield {
                            "event": "tool_result",
                            "data": {
                                "name": tc_name or "unknown",
                                "content": tc_content,
                                "tool_call_id": getattr(msg_chunk, "tool_call_id", ""),
                            },
                        }
                        # Include tool result in full content
                        if tc_content:
                            full_content += tc_content

                    content = getattr(msg_chunk, "content", "")
                    if content and isinstance(content, str):
                        full_content += content
                        yield {"event": "token", "data": {"token": content, "content": content}}
            else:
                # Direct chat streaming (no tools)
                async for chunk in llm.astream(langchain_messages):
                    content = chunk.content if hasattr(chunk, "content") else str(chunk)
                    if content:
                        full_content += content
                        yield {"event": "token", "data": {"token": content, "content": content}}

            # Save assistant message
            assistant_msg = ChatMessage(
                conversation_id=conversation_id,
                user_id=user_id,
                role="assistant",
                content=full_content,
            )
            await self.save_message(assistant_msg)

            # Persist to long-term memory (every N messages, check on even exchanges)
            if conv and conv.message_count % settings.HINDSIGHT_REFLECTION_INTERVAL == 0:
                await self.memory.persist_to_long_term(user_id, [
                    {"role": "user", "content": message, "conversation_id": conversation_id},
                    {"role": "assistant", "content": full_content, "conversation_id": conversation_id},
                ])

            yield {
                "event": "done",
                "data": {
                    "message_id": assistant_msg.id,
                    "content": full_content,
                },
            }

        except Exception as e:
            logger.exception(f"Stream error for conv {conversation_id}: {e}")
            yield {"event": "error", "data": {"error": str(e)}}

    async def _get_system_prompt(self, conversation_id: str) -> str:
        """Get the system prompt for a conversation."""
        try:
            doc = await self.conversations_col.find_one({"id": conversation_id})
            if doc and doc.get("system_prompt"):
                return doc["system_prompt"]
        except Exception:
            pass
        return DEFAULT_SYSTEM_PROMPT.format(
            current_time=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        )


# ── Module-level singleton ──────────────────────────────────

_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    if _chat_service is None:
        raise RuntimeError("ChatService not initialized. Call init_chat_service() first.")
    return _chat_service


async def init_chat_service(memory_manager: MemoryManager) -> ChatService:
    global _chat_service
    _chat_service = ChatService(memory_manager)
    logger.info("✅ ChatService initialized")
    return _chat_service


# ── Helpers ──────────────────────────────────────────────────

def _iso(dt) -> str:
    if dt is None:
        return ""
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


def _extract_usage(response) -> Optional[dict]:
    """Extract token usage from LangChain response."""
    try:
        if hasattr(response, "response_metadata"):
            meta = response.response_metadata
            if "token_usage" in meta:
                tu = meta["token_usage"]
                return {
                    "prompt": tu.get("prompt_tokens", 0),
                    "completion": tu.get("completion_tokens", 0),
                    "total": tu.get("total_tokens", 0),
                }
        if hasattr(response, "usage_metadata"):
            um = response.usage_metadata
            return {
                "prompt": um.get("input_tokens", 0),
                "completion": um.get("output_tokens", 0),
                "total": um.get("total_tokens", 0),
            }
    except Exception:
        pass
    return None


def _build_langchain_messages(
    buffer: List[Dict],
    current_message: str,
    system_prompt: str,
) -> List:
    """
    Build LangChain message list from buffer + current message + system prompt.
    """
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    messages = [SystemMessage(content=system_prompt)]

    for msg in buffer:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    # Add current message (not yet in buffer)
    if not buffer or buffer[-1].get("role") != "user" or buffer[-1].get("content") != current_message:
        messages.append(HumanMessage(content=current_message))

    return messages
