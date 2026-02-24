"""ChatPanel widget - LLM chat with streaming and markdown rendering."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Markdown, Static

from src.tui.commands import COMMANDS, parse_command


class ChatPanel(Widget):
    """Chat panel with input, message history, and LLM streaming."""

    DEFAULT_CSS = """
    ChatPanel {
        height: 100%;
        width: 100%;
        layout: vertical;
    }
    ChatPanel #chat-messages {
        height: 1fr;
        padding: 0 1;
    }
    ChatPanel .chat-user {
        color: $accent;
        margin: 1 0 0 0;
    }
    ChatPanel .chat-assistant {
        margin: 0 0 0 2;
    }
    ChatPanel .chat-error {
        color: $error;
        margin: 0 0 0 2;
    }
    ChatPanel .chat-info {
        color: $text-muted;
        content-align: center middle;
        margin: 1 0;
    }
    ChatPanel .chat-system {
        color: $text-muted;
        margin: 0 0 0 2;
    }
    ChatPanel #chat-input {
        dock: bottom;
        margin: 0;
    }
    """

    class AnalysisRequested(Message):
        """Posted when auto-analysis text should be sent to chat."""

        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()

    class ChatReady(Message):
        """Posted when the chat panel is initialized and ready."""

    class CommandRequested(Message):
        """Posted when a slash command should be handled by the app."""

        def __init__(self, command: str, args: str) -> None:
            self.command = command
            self.args = args
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._provider = None
        self._history = None
        self._streaming = False
        self._current_predictions: list[dict] | None = None
        self._response_widget: Markdown | None = None
        self._accumulated_response = ""

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="chat-messages")
        yield Input(
            placeholder="Skriv melding eller /kommando...",
            id="chat-input",
        )

    def on_mount(self) -> None:
        self._init_provider()

    def _init_provider(self) -> None:
        """Initialize LLM provider and chat history."""
        from src.chat.history import ChatHistory

        self._history = ChatHistory()

        try:
            from src.chat.providers import create_provider

            self._provider = create_provider()
            self._add_info(f"Chat klar ({self._provider.name})")
        except RuntimeError as e:
            self._add_info(str(e))

        # Load recent history into view
        if self._history:
            recent = self._history.get_recent(limit=20)
            for msg in recent:
                if msg.role == "user":
                    self._add_user_bubble(msg.content)
                elif msg.role == "assistant":
                    self._add_assistant_bubble(msg.content)

        self.post_message(self.ChatReady())

    def show_welcome_message(self) -> None:
        """Show a welcome message with auto-detected system state."""
        base_dir = Path(__file__).parent.parent.parent.parent
        db_path = base_dir / "data" / "processed" / "betbot.db"
        report_path = base_dir / "reports" / "latest_training_report.json"
        model_dir = base_dir / "models"

        # Check data state
        match_count = 0
        league_count = 0
        latest_date = None

        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))

                row = conn.execute("SELECT COUNT(*) FROM matches").fetchone()
                if row and row[0]:
                    match_count = row[0]

                row = conn.execute(
                    "SELECT COUNT(DISTINCT league_id) FROM matches"
                ).fetchone()
                if row and row[0]:
                    league_count = row[0]

                row = conn.execute("SELECT MAX(date_unix) FROM matches").fetchone()
                if row and row[0]:
                    latest_date = datetime.fromtimestamp(row[0])

                conn.close()
            except Exception:
                pass

        has_data = match_count > 0

        # Check model state
        model_path = model_dir / "match_predictor.pkl"
        has_model = model_path.exists()

        # Check data staleness
        stale_days = None
        if latest_date:
            stale_days = (datetime.now() - latest_date).days

        # Build welcome message
        lines = ["Velkommen til BetBot!", ""]

        if not has_data:
            lines.append(
                "Ingen data funnet. Bruk /download for aa laste ned kampdata fra FootyStats."
            )
        elif stale_days is not None and stale_days > 30:
            lines.append(
                f"Data er {stale_days} dager gammel "
                f"(siste: {latest_date.strftime('%Y-%m-%d')})."
            )
            lines.append("Bruk /download for aa oppdatere.")
            if not has_model:
                lines.append("Ingen modell funnet. Bruk /train etter oppdatering.")
        elif not has_model:
            lines.append(
                f"Data: {match_count:,} kamper fra {league_count} ligaer "
                f"(siste: {latest_date.strftime('%Y-%m-%d')})."
            )
            lines.append("Ingen modell funnet. Bruk /train for aa trene ML-modeller.")
        else:
            lines.append(
                f"Data: {match_count:,} kamper fra {league_count} ligaer "
                f"(siste: {latest_date.strftime('%Y-%m-%d')})."
            )
            lines.append("Modell klar. Bruk /predict for aa finne value bets.")

        lines.append("")
        lines.append("Skriv /help for alle kommandoer.")

        self._add_system_message("\n".join(lines))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "chat-input":
            return

        text = event.value.strip()
        if not text:
            return

        event.input.value = ""

        # Check for slash commands before LLM flow
        cmd = parse_command(text)
        if cmd is not None:
            self._handle_command(cmd)
            return

        if self._streaming:
            return

        if not self._provider:
            self._add_error("Ingen LLM-provider konfigurert. Sett ANTHROPIC_API_KEY eller OPENAI_API_KEY i .env")
            return

        self._add_user_bubble(text)
        self._save_message("user", text)
        self._stream_response(text)

    def _handle_command(self, cmd) -> None:
        """Route a parsed ChatCommand to the appropriate handler."""
        if cmd.name == "clear":
            self._clear_chat()
        elif cmd.name == "help":
            self._show_help()
        elif cmd.name in ("download", "train", "predict", "status"):
            self._add_user_bubble(f"/{cmd.name}" + (f" {cmd.args}" if cmd.args else ""))
            self.post_message(self.CommandRequested(cmd.name, cmd.args))
        elif cmd.name in COMMANDS:
            # Any other known command that might be added later
            self._add_user_bubble(f"/{cmd.name}" + (f" {cmd.args}" if cmd.args else ""))
            self.post_message(self.CommandRequested(cmd.name, cmd.args))
        else:
            self._add_user_bubble(f"/{cmd.name}" + (f" {cmd.args}" if cmd.args else ""))
            self._add_error(f"Ukjent kommando: /{cmd.name}. Skriv /help for kommandoer.")

    def _show_help(self) -> None:
        """Render the help text inline as a system message."""
        self._add_user_bubble("/help")
        lines = ["Tilgjengelige kommandoer:", ""]
        for name, description in COMMANDS.items():
            lines.append(f"  /{name} - {description}")
        help_text = "\n".join(lines)
        self._add_system_message(help_text)

    def render_predictions_inline(self, picks: list[dict], stale_warning: str | None = None) -> None:
        """Render prediction results as a Markdown table inline in chat."""
        if stale_warning:
            self._add_system_message(f"⚠ {stale_warning}")

        if not picks:
            self._add_system_message("Ingen value bets funnet.")
            return

        lines = ["**Value Bets**", ""]
        lines.append("| Kamp | Market | Edge | Konf. |")
        lines.append("|------|--------|------|-------|")
        for p in picks:
            home = p.get("home_team", "?")
            away = p.get("away_team", "?")
            market = p.get("market", "?")
            edge = p.get("edge")
            edge_str = f"{edge:.1%}" if edge is not None else "-"
            conf = p.get("confidence", "-")
            lines.append(f"| {home} - {away} | {market} | {edge_str} | {conf} |")

        md = "\n".join(lines)
        container = self.query_one("#chat-messages", VerticalScroll)
        widget = Markdown(md, classes="chat-assistant")
        container.mount(widget)
        container.scroll_end(animate=False)

    def render_training_report_inline(self, report: dict) -> None:
        """Render training report as a Markdown table inline in chat."""
        perf = report.get("model_performance", {})
        data = report.get("data_stats", {})
        duration = report.get("total_duration_seconds")

        lines = ["**Treningsrapport**", ""]

        total = data.get("total_matches", "?")
        features = data.get("features_generated", "?")
        lines.append(f"Kamper: {total:,} | Features: {features:,}")
        if duration is not None:
            lines.append(f"Tid: {duration:.0f}s")
        lines.append("")

        lines.append("| Modell | Accuracy | Log Loss |")
        lines.append("|--------|----------|----------|")
        for key, label in [("result_1x2", "1X2"), ("over_25", "Over 2.5"), ("btts", "BTTS")]:
            m = perf.get(key, {})
            acc = m.get("accuracy")
            ll = m.get("log_loss")
            acc_str = f"{acc:.1%}" if acc is not None else "-"
            ll_str = f"{ll:.4f}" if ll is not None else "-"
            lines.append(f"| {label} | {acc_str} | {ll_str} |")

        md = "\n".join(lines)
        container = self.query_one("#chat-messages", VerticalScroll)
        widget = Markdown(md, classes="chat-assistant")
        container.mount(widget)
        container.scroll_end(animate=False)

    def render_system_message(self, text: str) -> None:
        """Render a system message inline in chat (public API for app)."""
        self._add_system_message(text)

    def send_auto_analysis(self, predictions: list[dict]) -> None:
        """Trigger automatic analysis of predictions."""
        self._current_predictions = predictions

        if not self._provider:
            return

        if self._streaming:
            return

        prompt = "Analyser dagens value bets. Gi en kort oppsummering av de beste mulighetene."
        self._add_user_bubble(prompt)
        self._save_message("user", prompt)
        self._stream_response(prompt)

    @work
    async def _stream_response(self, user_text: str) -> None:
        """Stream LLM response in an async worker."""
        from src.chat.llm_provider import ChatMessage
        from src.chat.system_prompt import build_system_prompt

        self._streaming = True
        input_widget = self.query_one("#chat-input", Input)
        input_widget.disabled = True

        # Build message list
        system = build_system_prompt(predictions=self._current_predictions)
        messages = [ChatMessage(role="system", content=system)]

        # Add recent history
        if self._history:
            messages.extend(self._history.get_recent(limit=20))

        # Create response widget
        self._accumulated_response = ""
        self._response_widget = Markdown("...", classes="chat-assistant")
        container = self.query_one("#chat-messages", VerticalScroll)
        await container.mount(self._response_widget)
        container.scroll_end(animate=False)

        try:
            async for token in self._provider.stream_response(messages):
                self._accumulated_response += token
                await self._response_widget.update(self._accumulated_response)
                container.scroll_end(animate=False)

            # Save complete response
            self._save_message("assistant", self._accumulated_response)

        except Exception as e:
            error_msg = f"Feil: {e}"
            if self._accumulated_response:
                # Keep partial response, add error below
                self._save_message("assistant", self._accumulated_response)
                self._add_error(error_msg)
            else:
                # Remove empty response widget, show error
                await self._response_widget.remove()
                self._add_error(error_msg)
        finally:
            self._streaming = False
            self._response_widget = None
            input_widget.disabled = False
            input_widget.focus()

    def _add_user_bubble(self, text: str) -> None:
        container = self.query_one("#chat-messages", VerticalScroll)
        widget = Static(f"> {text}", classes="chat-user")
        container.mount(widget)
        container.scroll_end(animate=False)

    def _add_assistant_bubble(self, text: str) -> None:
        container = self.query_one("#chat-messages", VerticalScroll)
        widget = Markdown(text, classes="chat-assistant")
        container.mount(widget)
        container.scroll_end(animate=False)

    def _add_error(self, text: str) -> None:
        container = self.query_one("#chat-messages", VerticalScroll)
        widget = Static(text, classes="chat-error")
        container.mount(widget)
        container.scroll_end(animate=False)

    def _add_info(self, text: str) -> None:
        container = self.query_one("#chat-messages", VerticalScroll)
        widget = Static(text, classes="chat-info")
        container.mount(widget)
        container.scroll_end(animate=False)

    def _add_system_message(self, text: str) -> None:
        container = self.query_one("#chat-messages", VerticalScroll)
        widget = Static(text, classes="chat-system")
        container.mount(widget)
        container.scroll_end(animate=False)

    def _save_message(self, role: str, content: str) -> None:
        if self._history:
            from src.chat.llm_provider import ChatMessage

            self._history.add(ChatMessage(role=role, content=content))

    def _clear_chat(self) -> None:
        if self._history:
            self._history.clear()
        container = self.query_one("#chat-messages", VerticalScroll)
        container.remove_children()
        self._add_info("Chat nullstilt")

    def cleanup(self) -> None:
        """Close database connections."""
        if self._history:
            self._history.close()
