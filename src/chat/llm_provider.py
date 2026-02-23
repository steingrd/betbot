"""LLM Provider protocol and ChatMessage dataclass."""

from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Protocol, runtime_checkable


@dataclass
class ChatMessage:
    """A single chat message."""

    role: str  # "user", "assistant", "system"
    content: str


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM providers with async streaming."""

    @property
    def name(self) -> str:
        """Human-readable provider name (e.g. 'Claude', 'GPT-4o')."""
        ...

    async def stream_response(
        self, messages: list[ChatMessage]
    ) -> AsyncIterator[str]:
        """Stream response tokens for the given message history.

        Args:
            messages: List of ChatMessage (system, user, assistant).

        Yields:
            String tokens as they arrive.
        """
        ...
