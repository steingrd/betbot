"""PredictionsView widget - shows value bet predictions in the Predictions tab."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Static


class PredictionsView(Widget):
    """Shows value bet predictions in a DataTable."""

    DEFAULT_CSS = """
    PredictionsView {
        height: 100%;
        width: 100%;
    }
    PredictionsView DataTable {
        height: 1fr;
    }
    PredictionsView .predictions-empty {
        width: 100%;
        height: 100%;
        content-align: center middle;
        color: $text-muted;
    }
    PredictionsView .predictions-stale {
        width: 100%;
        height: auto;
        background: $warning 20%;
        color: $warning;
        padding: 0 2;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._has_data = False

    def compose(self) -> ComposeResult:
        yield Static(
            "Ingen predictions enda\n\nTrykk Ctrl+P for a kjore predictions\neller Ctrl+D for a laste ned data forst",
            id="predictions-empty",
            classes="predictions-empty",
        )
        yield Static("", id="predictions-stale", classes="predictions-stale")
        yield DataTable(id="predictions-table")

    def on_mount(self) -> None:
        table = self.query_one("#predictions-table", DataTable)
        table.add_columns("Tid", "Kamp", "Liga", "Marked", "Edge", "Konfidanse")
        table.display = False
        self.query_one("#predictions-stale").display = False

    def show_picks(self, picks: list[dict], stale_warning: str | None = None) -> None:
        """Populate the table with prediction results."""
        table = self.query_one("#predictions-table", DataTable)
        table.clear()

        if not picks:
            self.query_one("#predictions-empty").display = True
            self.query_one("#predictions-empty", Static).update(
                "Ingen value bets funnet\n\nModellen fant ingen kamper med tilstrekkelig edge"
            )
            table.display = False
            self.query_one("#predictions-stale").display = False
            self._has_data = False
            return

        self.query_one("#predictions-empty").display = False
        table.display = True
        self._has_data = True

        # Show stale warning if applicable
        stale_widget = self.query_one("#predictions-stale", Static)
        if stale_warning:
            stale_widget.update(stale_warning)
            stale_widget.display = True
        else:
            stale_widget.display = False

        for pick in picks:
            kickoff = pick.get("kickoff", "--:--")
            match_label = f"{pick['home_team']} vs {pick['away_team']}"
            league = pick.get("league", "-")
            market = pick.get("market", "-")

            edge = pick.get("edge")
            edge_str = f"{edge:.1%}" if edge is not None else "-"

            confidence = pick.get("confidence", "-")

            table.add_row(kickoff, match_label, league, market, edge_str, confidence)

    def set_empty(self) -> None:
        """Reset to empty state."""
        self.query_one("#predictions-empty").display = True
        self.query_one("#predictions-empty", Static).update(
            "Ingen predictions enda\n\nTrykk Ctrl+P for a kjore predictions\neller Ctrl+D for a laste ned data forst"
        )
        self.query_one("#predictions-table", DataTable).display = False
        self.query_one("#predictions-stale").display = False
        self._has_data = False
