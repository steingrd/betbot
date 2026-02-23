"""BetBot TUI Application - Main app with multi-panel layout."""

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Footer,
    Input,
    Static,
    TabbedContent,
    TabPane,
)

from .widgets.status_bar import StatusBar
from .widgets.event_log import EventLog
from .widgets.football_spinner import FootballSpinner

MIN_WIDTH = 100
MIN_HEIGHT = 30


class BetBotApp(App):
    """BetBot TUI - Value bet analysis dashboard."""

    TITLE = "BetBot"
    CSS_PATH = "styles/app.tcss"

    BINDINGS = [
        Binding("ctrl+d", "download_data", "Last ned data", show=True),
        Binding("ctrl+t", "train_model", "Tren modell", show=True),
        Binding("ctrl+p", "run_predictions", "Predictions", show=True),
        Binding("ctrl+q", "quit_app", "Avslutt", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield StatusBar()
        with Horizontal(id="main-content"):
            with Vertical(id="tab-area"):
                with TabbedContent(id="tabs"):
                    with TabPane("Predictions", id="tab-predictions"):
                        yield Static(
                            "Ingen predictions ennå\n\nTrykk Ctrl+P for å kjøre predictions\neller Ctrl+D for å laste ned data først",
                            classes="empty-state",
                        )
                    with TabPane("Data", id="tab-data"):
                        yield Static(
                            "Ingen data lastet\n\nTrykk Ctrl+D for å laste ned data",
                            classes="empty-state",
                        )
                    with TabPane("Trening", id="tab-training"):
                        yield Static(
                            "Ingen treningsresultater\n\nTrykk Ctrl+T for å trene modellen",
                            classes="empty-state",
                        )
            with Vertical(id="right-panel"):
                yield EventLog(id="event-log", markup=True)
                yield FootballSpinner(id="spinner")
        with Horizontal(id="chat-area"):
            yield Input(
                placeholder="Skriv en melding til BetBot...",
                id="chat-input",
            )
        yield Static(
            "Terminal for liten (minimum 100x30)",
            id="size-warning",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._event_log.log_info("BetBot startet")
        self._check_terminal_size()

    def on_resize(self) -> None:
        self._check_terminal_size()

    def _check_terminal_size(self) -> None:
        warning = self.query_one("#size-warning", Static)
        too_small = self.size.width < MIN_WIDTH or self.size.height < MIN_HEIGHT
        warning.display = too_small

    @property
    def _event_log(self) -> EventLog:
        return self.query_one("#event-log", EventLog)

    @property
    def _spinner(self) -> FootballSpinner:
        return self.query_one("#spinner", FootballSpinner)

    @property
    def _status_bar(self) -> StatusBar:
        return self.query_one(StatusBar)

    # --- Actions (Phase 1: log-only stubs) ---

    def action_download_data(self) -> None:
        self._event_log.log_info("Datanedlasting ikke implementert ennå (Phase 2)")

    def action_train_model(self) -> None:
        self._event_log.log_info("Modelltrening ikke implementert ennå (Phase 3)")

    def action_run_predictions(self) -> None:
        self._event_log.log_info("Predictions ikke implementert ennå (Phase 4)")

    def action_quit_app(self) -> None:
        self._event_log.log_info("Avslutter BetBot...")
        self.exit()
