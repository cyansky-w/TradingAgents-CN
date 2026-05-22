"""
Chat LLM factory — creates LangChain-compatible chat models using the project's
existing LLM provider infrastructure (tradingagents.llm_clients).

Reads provider config from MongoDB (llm_providers / system_configs), resolves
API keys via env vars (ENV > DB), and returns a streaming-enabled chat model.
"""

import os
import re
import logging
from typing import Optional, Tuple

from app.services.config_service import config_service
from app.core.config import settings

logger = logging.getLogger("webapi.chat")


async def get_chat_llm_config() -> Tuple[str, str, str, str, str]:
    """
    Resolve the effective LLM config for chat.

    Returns: (provider, model_name, api_key, base_url, display_name)
    """
    # 1. Check if a specific chat model is configured
    if settings.CHAT_DEFAULT_MODEL:
        provider_name, model = _parse_model_spec(settings.CHAT_DEFAULT_MODEL)
    else:
        provider_name, model = None, None

    # 2. If not configured, fall back to system default provider + model
    if not provider_name or not model:
        try:
            eff_settings = await _get_effective_settings()
            provider_name = provider_name or eff_settings.get("default_provider", "openai")
            model = model or eff_settings.get("default_model") or eff_settings.get("quick_analysis_model") or "gpt-3.5-turbo"
        except Exception as e:
            logger.warning(f"Could not read effective settings, using fallback: {e}")
            provider_name = provider_name or "openai"
            model = model or "gpt-4o-mini"

    # 3. Look up provider credentials from llm_providers collection
    api_key, base_url, display_name = await _resolve_provider_credentials(provider_name)

    return provider_name, model, api_key, base_url, display_name


async def create_chat_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    streaming: bool = True,
    extra_body: Optional[dict] = None,
):
    """
    Create a streaming-enabled LangChain chat model from project config.

    Reuses tradingagents.llm_clients (OpenAIClient / GoogleClient / AnthropicClient)
    for consistent content normalization and provider handling.

    Parameters
    ----------
    extra_body : dict, optional
        Extra parameters passed to the LLM's request body (via OpenAI SDK extra_body).
        E.g. ``{"thinking": {"type": "disabled"}}`` disables DeepSeek thinking mode.
    """
    if not provider or not model:
        provider, model, api_key, base_url, _ = await get_chat_llm_config()
    else:
        api_key, base_url, _ = await _resolve_provider_credentials(provider)

    provider_lower = provider.lower()

    # Build kwargs for the underlying client
    client_kwargs: dict = dict(
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if extra_body:
        client_kwargs["extra_body"] = extra_body
    if api_key:
        client_kwargs["api_key"] = api_key

    prov_type = _classify_provider(provider_lower)

    if prov_type == "openai_compat":
        from tradingagents.llm_clients.openai_client import OpenAIClient

        if not base_url and not api_key:
            api_key = _fallback_api_key(provider_lower)
            client_kwargs["api_key"] = api_key

        client = OpenAIClient(
            model=model,
            base_url=base_url or None,
            provider=provider_lower,
            **client_kwargs,
        )
        llm = client.get_llm()
        llm.streaming = streaming
        logger.info(f"Creating chat LLM via OpenAIClient: model={model}, base_url={base_url or 'default'}, extra_body={extra_body}")
        return llm

    elif prov_type == "google":
        from tradingagents.llm_clients.google_client import GoogleClient

        if not api_key:
            api_key = os.getenv("GOOGLE_API_KEY", "")
            client_kwargs["api_key"] = api_key

        client = GoogleClient(
            model=model,
            base_url=base_url or None,
            **client_kwargs,
        )
        llm = client.get_llm()
        llm.streaming = streaming
        logger.info(f"Creating chat LLM via GoogleClient: model={model}")
        return llm

    elif prov_type == "anthropic":
        from tradingagents.llm_clients.anthropic_client import AnthropicClient

        if not api_key:
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
            client_kwargs["api_key"] = api_key

        client = AnthropicClient(
            model=model,
            base_url=base_url or None,
            **client_kwargs,
        )
        llm = client.get_llm()
        llm.streaming = streaming
        logger.info(f"Creating chat LLM via AnthropicClient: model={model}")
        return llm

    raise ValueError(f"Unsupported chat provider: {provider}")


def _classify_provider(provider: str) -> str:
    """Classify a provider as openai_compat, google, or anthropic."""
    if provider == "google":
        return "google"
    if provider == "anthropic":
        return "anthropic"
    return "openai_compat"


async def _resolve_provider_credentials(provider_name: str) -> Tuple[str, str, str]:
    """Look up API key, base URL, and display name for a provider from DB."""
    try:
        providers = await config_service.get_llm_providers()
        for p in providers:
            if (p.name or "").lower() == provider_name.lower():
                api_key = p.api_key or ""
                base_url = (p.default_base_url or "").rstrip("/")
                # Ensure the URL has a version path (e.g., /v1) for OpenAI-compatible APIs
                if base_url and not re.search(r'/v\d+$', base_url):
                    base_url += "/v1"
                display = p.display_name or p.name
                return api_key, base_url, display
    except Exception as e:
        logger.warning(f"Could not look up provider credentials: {e}")

    return "", "", provider_name


def _fallback_api_key(provider: str) -> str:
    """Try common env var patterns for a provider's API key."""
    from tradingagents.llm_clients.provider_keys import env_key_for_provider

    key = env_key_for_provider(provider)
    if key:
        return os.getenv(key, "")
    return os.getenv(f"{provider.upper()}_API_KEY", "")


def _parse_model_spec(spec: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse 'provider:model' or 'provider/model' format."""
    for sep in (":", "/"):
        if sep in spec:
            parts = spec.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    return None, spec.strip()


async def _get_effective_settings() -> dict:
    """Read effective system settings (file → DB → default)."""
    try:
        from app.services.config_provider import provider as cfg_provider
        return await cfg_provider.get_effective_system_settings()
    except Exception:
        from config import load_json_config
        try:
            return load_json_config("settings.json")
        except Exception:
            return {}
