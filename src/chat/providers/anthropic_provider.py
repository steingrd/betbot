"""Anthropic Claude provider with async streaming."""

from __future__ import annotations

from typing import AsyncIterator

from ..llm_provider import ChatMessage


class AnthropicProvider:
    """LLM provider using Anthropic's Claude API."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    @property
    def name(self) -> str:
        return f"Claude ({self._model.split('-')[1]})"

    async def stream_response(
        self, messages: list[ChatMessage]
    ) -> AsyncIterator[str]:
        """Stream response tokens from Claude."""
        # Separate system message from conversation
        system_text = ""
        conversation = []
        for msg in messages:
            if msg.role == "system":
                system_text = msg.content
            else:
                conversation.append({"role": msg.role, "content": msg.content})

        async with self._client.messages.stream(
            model=self._model,
            max_tokens=2048,
            system=system_text or "Du er en hjelpsom assistent.",
            messages=conversation,
        ) as stream:
            async for text in stream.text_stream:
                yield text
