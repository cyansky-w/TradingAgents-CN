"""
SSE streaming generator for AI chat.

Follows the pattern established in app/routers/sse.py for task progress streaming.
Events: token, tool_call, tool_result, done, error, heartbeat.
"""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Optional

from app.core.config import settings

logger = logging.getLogger("webapi.chat.sse")


async def chat_event_generator(
    conversation_id: str,
    user_id: str,
    message: str,
    chat_service,  # ChatService instance (avoids circular import)
) -> AsyncGenerator[str, None]:
    """
    SSE generator for chat message streaming.

    Args:
        conversation_id: Target conversation ID
        user_id: Authenticated user ID
        message: User's message text
        chat_service: ChatService instance

    Yields:
        SSE-formatted strings: "event: <type>\ndata: <json>\n\n"
    """
    # Load dynamic SSE settings
    try:
        from app.services.config_provider import provider as config_provider

        eff = await config_provider.get_effective_system_settings()
        poll_timeout = float(
            eff.get("chat_sse_poll_timeout_seconds", settings.CHAT_SSE_POLL_TIMEOUT_SECONDS)
        )
        heartbeat_every = int(
            eff.get("chat_sse_heartbeat_interval_seconds", settings.CHAT_SSE_HEARTBEAT_INTERVAL_SECONDS)
        )
        max_idle = int(
            eff.get("chat_sse_max_idle_seconds", settings.CHAT_SSE_MAX_IDLE_SECONDS)
        )
    except Exception:
        poll_timeout = settings.CHAT_SSE_POLL_TIMEOUT_SECONDS
        heartbeat_every = settings.CHAT_SSE_HEARTBEAT_INTERVAL_SECONDS
        max_idle = settings.CHAT_SSE_MAX_IDLE_SECONDS

    try:
        # Send connection confirmation
        yield _sse_event("connected", {
            "conversation_id": conversation_id,
            "message": "Chat stream connected",
        })

        # Stream the LLM response
        stream_generator = chat_service.stream_response(
            user_id=user_id,
            conversation_id=conversation_id,
            message=message,
        )

        idle_elapsed = 0.0
        last_hb = time.monotonic()

        async for event in stream_generator:
            idle_elapsed = 0.0  # reset idle timer on data

            event_type = event.get("event", "token")
            event_data = event.get("data", {})

            yield _sse_event(event_type, event_data)

            if event_type in ("done", "error"):
                return

        # If stream ended without explicit done, send done
        yield _sse_event("done", {"status": "completed"})

    except asyncio.CancelledError:
        logger.info(f"Chat SSE cancelled: conv={conversation_id}")
        yield _sse_event("error", {"error": "Stream cancelled"})
    except Exception as e:
        logger.exception(f"Chat SSE error for conv {conversation_id}: {e}")
        yield _sse_event("error", {"error": str(e)})


def _sse_event(event: str, data: dict) -> str:
    """Format an SSE event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
