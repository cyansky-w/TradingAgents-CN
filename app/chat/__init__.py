"""
AI Chat Module

Provides conversation management, SSE streaming, LLM integration, tool registry,
and optional long-term memory via Hindsight.

Architecture:
    router.py  ──► service.py  ──► llm_factory.py
                        │              └── wraps tradingagents LLM infra
                        ├── memory_manager.py (Redis buffer + Hindsight)
                        └── tool_registry.py (LangChain BaseTool pattern)
"""

from app.chat.router import router
from app.chat.service import ChatService
from app.chat.memory_manager import MemoryManager
from app.chat.tool_registry import tool_registry
from app.chat.schemas import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    MessageResponse,
    ChatRequest,
)
