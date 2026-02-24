"""LLM provider factory - selects provider based on available API keys."""

from __future__ import annotations

import os

from ..llm_provider import LLMProvider


def create_provider() -> LLMProvider:
    """Create an LLM provider based on available API keys.

    Checks for ANTHROPIC_API_KEY first, then OPENAI_API_KEY.

    Raises:
        RuntimeError: If no API key is configured.
    """
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")

    if anthropic_key:
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(api_key=anthropic_key)

    if openai_key:
        from .openai_provider import OpenAIProvider

        return OpenAIProvider(api_key=openai_key)

    raise RuntimeError(
        "Ingen LLM API-nokkel funnet. "
        "Sett ANTHROPIC_API_KEY eller OPENAI_API_KEY i .env"
    )
