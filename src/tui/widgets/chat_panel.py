"""ChatPanel widget - LLM chat with streaming and markdown rendering."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Markdown, Static


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
            placeholder="Skriv en melding til BetBot...",
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

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "chat-input":
            return

        text = event.value.strip()
        if not text:
            return

        event.input.value = ""

        if text == "/clear":
            self._clear_chat()
            return

        if self._streaming:
            return

        if not self._provider:
            self._add_error("Ingen LLM-provider konfigurert. Sett ANTHROPIC_API_KEY eller OPENAI_API_KEY i .env")
            return

        self._add_user_bubble(text)
        self._save_message("user", text)
        self._stream_response(text)

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
