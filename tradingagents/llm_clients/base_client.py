from abc import ABC, abstractmethod
from typing import Any, Optional
import logging
import warnings

logger = logging.getLogger(__name__)


def _strip_reasoning(message) -> None:
    """Strip reasoning_content from a message object.

    Verified in langchain-openai 1.1.9: both _convert_dict_to_message (receive)
    and _convert_delta_to_message_chunk (stream receive) ignore reasoning_content
    from the API response entirely.  _convert_message_to_dict (send) also does
    not include it.  As a result, reasoning_content is lost on round-trip, and
    DeepSeek rejects follow-up calls with 400.

    The fix for DeepSeek + tool-calling is disabling thinking mode via
    extra_body={"thinking": {"type": "disabled"}} in llm_factory.create_chat_llm().

    This function remains as a safety net for future langchain-openai versions
    that may start preserving reasoning_content.
    """
    for attr in ("additional_kwargs", "response_metadata"):
        if hasattr(message, attr):
            d = getattr(message, attr)
            if isinstance(d, dict) and "reasoning_content" in d:
                del d["reasoning_content"]


def normalize_content(response):
    """Normalize typed content blocks returned by some providers to plain text.
    Also strips reasoning_content so DeepSeek thinking-mode models don't
    require it echoed back on subsequent calls."""
    _strip_reasoning(response)

    content = getattr(response, "content", None)
    if isinstance(content, list):
        texts = [
            item.get("text", "") if isinstance(item, dict) and item.get("type") == "text"
            else item if isinstance(item, str) else ""
            for item in content
        ]
        response.content = "\n".join(text for text in texts if text)
    return response


class BaseLLMClient(ABC):
    """Minimal provider wrapper used by CLI and future graph integration."""

    def __init__(self, model: str, base_url: Optional[str] = None, **kwargs):
        self.model = model
        self.base_url = base_url
        self.kwargs = kwargs

    def get_provider_name(self) -> str:
        provider = getattr(self, "provider", None)
        if provider:
            return str(provider)
        return self.__class__.__name__.removesuffix("Client").lower()

    def warn_if_unknown_model(self) -> None:
        if self.validate_model():
            return

        warnings.warn(
            (
                f"Model '{self.model}' is not in the known model list for "
                f"provider '{self.get_provider_name()}'. Continuing anyway."
            ),
            RuntimeWarning,
            stacklevel=2,
        )

    @abstractmethod
    def get_llm(self) -> Any:
        """Return the configured LangChain client."""

    @abstractmethod
    def validate_model(self) -> bool:
        """Return whether the model is known for the provider."""
