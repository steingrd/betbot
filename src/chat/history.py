"""Chat history persistence with SQLite."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .llm_provider import ChatMessage

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "chat.db"


class ChatHistory:
    """SQLite-backed chat history."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.commit()

    def add(self, message: ChatMessage) -> None:
        """Add a message to history."""
        self._conn.execute(
            "INSERT INTO messages (role, content) VALUES (?, ?)",
            (message.role, message.content),
        )
        self._conn.commit()

    def get_recent(self, limit: int = 20) -> list[ChatMessage]:
        """Get the most recent messages for context window.

        Args:
            limit: Max number of messages to return.

        Returns:
            Messages in chronological order.
        """
        rows = self._conn.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [ChatMessage(role=r[0], content=r[1]) for r in reversed(rows)]

    def clear(self) -> None:
        """Delete all messages."""
        self._conn.execute("DELETE FROM messages")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
