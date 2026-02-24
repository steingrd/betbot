"""ActivityPanel widget - shows current running task with animated spinner."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from .football_spinner import FootballSpinner


class ActivityPanel(Widget):
    """Displays the current running task with an animated football spinner."""

    DEFAULT_CSS = """
    ActivityPanel {
        height: 8;
        padding: 0 1;
    }
    ActivityPanel .ap-title {
        text-style: bold;
        margin-bottom: 1;
    }
    ActivityPanel .ap-content {
        layout: horizontal;
        height: auto;
    }
    ActivityPanel .ap-label {
        width: 1fr;
        height: auto;
        content-align: left middle;
        padding-top: 1;
    }
    ActivityPanel .ap-label-idle {
        width: 1fr;
        height: auto;
        content-align: left middle;
        padding-top: 1;
        color: $text-muted;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield Static("Aktivitet", classes="ap-title")
        with Widget(classes="ap-content"):
            yield FootballSpinner(id="ap-spinner")
            yield Static(
                "Ingen aktiv oppgave",
                id="ap-label",
                classes="ap-label-idle",
            )

    def on_mount(self) -> None:
        self.clear_task()

    def set_task(self, description: str) -> None:
        """Show spinner animating with the given task description."""
        try:
            spinner = self.query_one("#ap-spinner", FootballSpinner)
            spinner.active = True
            spinner.display = True

            label = self.query_one("#ap-label", Static)
            label.update(description)
            label.set_class(False, "ap-label-idle")
            label.set_class(True, "ap-label")
        except Exception:
            pass

    def clear_task(self) -> None:
        """Stop spinner and show idle state."""
        try:
            spinner = self.query_one("#ap-spinner", FootballSpinner)
            spinner.active = False
            spinner.display = False

            label = self.query_one("#ap-label", Static)
            label.update("Ingen aktiv oppgave")
            label.set_class(True, "ap-label-idle")
            label.set_class(False, "ap-label")
        except Exception:
            pass
