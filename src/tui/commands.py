"""Command parser for BetBot TUI chat commands."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChatCommand:
    """Parsed chat command with name and optional arguments."""

    name: str
    args: str


COMMANDS: dict[str, str] = {
    "download": "Last ned data fra FootyStats",
    "train": "Tren ML-modeller",
    "predict": "Finn value bets for kommende kamper",
    "help": "Vis tilgjengelige kommandoer",
    "clear": "Nullstill chat-historikk",
    "status": "Vis naavaerende status",
}


def parse_command(text: str) -> ChatCommand | None:
    """Parse a chat input string into a ChatCommand if it starts with /.

    Returns None if text does not start with /.
    Splits on first space: "/download foo" -> ChatCommand(name="download", args="foo").
    Returns ChatCommand for ANY /command (known or unknown).
    """
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None

    # Remove leading slash
    without_slash = stripped[1:]
    if not without_slash:
        return None

    # Split on first space
    parts = without_slash.split(None, 1)
    name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    return ChatCommand(name=name, args=args)
