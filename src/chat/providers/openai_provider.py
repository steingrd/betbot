"""OpenAI provider with async streaming."""

from __future__ import annotations

from typing import AsyncIterator

from ..llm_provider import ChatMessage


class OpenAIProvider:
    """LLM provider using OpenAI's API."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    @property
    def name(self) -> str:
        return f"OpenAI ({self._model})"

    async def stream_response(
        self, messages: list[ChatMessage]
    ) -> AsyncIterator[str]:
        """Stream response tokens from OpenAI."""
        api_messages = [{"role": m.role, "content": m.content} for m in messages]

        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=api_messages,
            max_tokens=2048,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
