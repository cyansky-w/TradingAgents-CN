"""
Memory manager for AI chat — two-tier architecture.

Tier 1 — Short-term Buffer (Redis):
    Stores last N messages per conversation for context window construction.
    Key: chat:buffer:{user_id}:{conversation_id}
    TTL: Configurable (default 24h)

Tier 2 — Long-term Memory (Hindsight, optional):
    Self-hosted memory service for persistent knowledge retention.
    Feature-gated via HINDSIGHT_ENABLED setting (default: false).
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger("webapi.chat.memory")


class MemoryManager:
    """Manages short-term (Redis) and long-term (Hindsight) memory for chat."""

    def __init__(self, redis_client):
        self.redis = redis_client
        self._hindsight_client: Optional["HindsightClient"] = None
        self._hindsight_enabled = settings.HINDSIGHT_ENABLED

        if self._hindsight_enabled:
            logger.info(
                f"🧠 Hindsight memory enabled: {settings.HINDSIGHT_API_URL}"
            )

    # ── Short-term Buffer (Redis) ────────────────────────────

    def _buffer_key(self, user_id: str, conv_id: str) -> str:
        return f"chat:buffer:{user_id}:{conv_id}"

    async def get_buffer(
        self, user_id: str, conv_id: str
    ) -> List[Dict[str, Any]]:
        """Retrieve buffered messages from Redis."""
        try:
            key = self._buffer_key(user_id, conv_id)
            raw_msgs = await self.redis.lrange(key, 0, -1)
            return [json.loads(m) for m in reversed(raw_msgs)]
        except Exception as e:
            logger.warning(f"Failed to read chat buffer: {e}")
            return []

    async def add_to_buffer(
        self, user_id: str, conv_id: str, message: Dict[str, Any]
    ) -> None:
        """Push a message into the Redis buffer, trimming to max size."""
        try:
            key = self._buffer_key(user_id, conv_id)
            pipe = self.redis.pipeline()
            pipe.lpush(key, json.dumps(message, ensure_ascii=False, default=str))
            pipe.ltrim(key, 0, settings.CHAT_MAX_CONTEXT_MESSAGES - 1)
            pipe.expire(key, settings.CHAT_REDIS_BUFFER_TTL)
            await pipe.execute()
        except Exception as e:
            logger.warning(f"Failed to write chat buffer: {e}")

    async def clear_buffer(self, user_id: str, conv_id: str) -> None:
        """Clear the buffer for a conversation."""
        try:
            key = self._buffer_key(user_id, conv_id)
            await self.redis.delete(key)
        except Exception as e:
            logger.warning(f"Failed to clear chat buffer: {e}")

    async def sync_buffer_from_db(
        self, user_id: str, conv_id: str, messages: List[Dict[str, Any]]
    ) -> None:
        """Rebuild Redis buffer from DB messages (e.g., after cold start)."""
        try:
            key = self._buffer_key(user_id, conv_id)
            await self.redis.delete(key)

            recent = messages[-settings.CHAT_MAX_CONTEXT_MESSAGES:]
            if recent:
                pipe = self.redis.pipeline()
                for msg in reversed(recent):
                    pipe.lpush(
                        key,
                        json.dumps(msg, ensure_ascii=False, default=str),
                    )
                pipe.expire(key, settings.CHAT_REDIS_BUFFER_TTL)
                await pipe.execute()
        except Exception as e:
            logger.warning(f"Failed to sync buffer from DB: {e}")

    # ── Long-term Memory (Hindsight) ─────────────────────────

    def set_hindsight(self, client: "HindsightClient") -> None:
        self._hindsight_client = client
        self._hindsight_enabled = True

    async def recall_long_term(
        self, user_id: str, query: str
    ) -> List[str]:
        """Recall relevant memories from Hindsight. Returns text snippets."""
        if not self._hindsight_enabled or not self._hindsight_client:
            return []

        try:
            bank_id = f"chat-user-{user_id}"
            results = await self._hindsight_client.recall(
                bank_id=bank_id,
                query=query,
                top_k=settings.HINDSIGHT_RECALL_TOP_K,
            )
            return [r.get("content", "") for r in results if r.get("content")]
        except Exception as e:
            logger.warning(f"Hindsight recall failed: {e}")
            return []

    async def persist_to_long_term(
        self, user_id: str, messages: List[Dict[str, Any]]
    ) -> None:
        """Persist chat messages to Hindsight for long-term retention."""
        if not self._hindsight_enabled or not self._hindsight_client:
            return

        try:
            bank_id = f"chat-user-{user_id}"
            for msg in messages:
                content = msg.get("content", "")
                if not content:
                    continue
                await self._hindsight_client.retain(
                    bank_id=bank_id,
                    content=content,
                    metadata={
                        "role": msg.get("role", "unknown"),
                        "conversation_id": msg.get("conversation_id", ""),
                    },
                )
        except Exception as e:
            logger.warning(f"Hindsight persist failed: {e}")

    async def reflect_long_term(self, user_id: str) -> Optional[str]:
        """Trigger Hindsight reflection over accumulated memories."""
        if not self._hindsight_enabled or not self._hindsight_client:
            return None

        try:
            bank_id = f"chat-user-{user_id}"
            result = await self._hindsight_client.reflect(
                bank_id=bank_id,
                query="Synthesize key patterns and insights from recent conversations.",
            )
            return result.get("content", "") if result else None
        except Exception as e:
            logger.warning(f"Hindsight reflect failed: {e}")
            return None


class HindsightClient:
    """
    Lightweight async HTTP client for the Hindsight memory API.

    Uses aiohttp for async HTTP; falls back to synchronous requests if unavailable.
    The full `hindsight-client` package can be installed later for richer features.
    """

    def __init__(self, base_url: str, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def retain(
        self, bank_id: str, content: str, metadata: Optional[Dict] = None
    ) -> Dict:
        """Store a memory in the given bank."""
        return await self._post("/api/retain", {
            "bank_id": bank_id,
            "content": content,
            "metadata": metadata or {},
        })

    async def recall(
        self, bank_id: str, query: str, top_k: int = 5
    ) -> List[Dict]:
        """Recall relevant memories."""
        result = await self._post("/api/recall", {
            "bank_id": bank_id,
            "query": query,
            "top_k": top_k,
        })
        if isinstance(result, list):
            return result
        return result.get("memories", result.get("results", []))

    async def reflect(self, bank_id: str, query: str) -> Dict:
        """Synthesize insights."""
        return await self._post("/api/reflect", {
            "bank_id": bank_id,
            "query": query,
        })

    async def _post(self, path: str, data: Dict) -> Any:
        import aiohttp

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = f"{self.base_url}{path}"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers, timeout=30) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.warning(f"Hindsight API error {resp.status}: {text}")
                    return {} if path != "/api/recall" else []
                return await resp.json()
