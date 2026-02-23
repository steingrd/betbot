"""DataTableView widget - shows downloaded data summary in the Data tab."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Static


class DataTableView(Widget):
    """Shows a summary of downloaded data grouped by league."""

    DEFAULT_CSS = """
    DataTableView {
        height: 100%;
    }
    DataTableView DataTable {
        height: 1fr;
    }
    DataTableView .no-data {
        width: 100%;
        height: 100%;
        content-align: center middle;
        color: $text-muted;
    }
    """

    def __init__(self, db_path: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._db_path = db_path or Path(__file__).parent.parent.parent.parent / "data" / "processed" / "betbot.db"

    def compose(self) -> ComposeResult:
        yield DataTable(id="data-summary-table")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Liga", "Land", "Sesonger", "Kamper", "Siste dato")
        self.refresh_data()

    def refresh_data(self) -> None:
        """Reload data from database and populate table."""
        table = self.query_one(DataTable)
        table.clear()

        if not self._db_path.exists():
            return

        try:
            conn = sqlite3.connect(str(self._db_path))
            rows = conn.execute("""
                SELECT
                    s.league_name,
                    s.country,
                    COUNT(DISTINCT s.id) as season_count,
                    COUNT(m.id) as match_count,
                    MAX(m.date_unix) as latest_date
                FROM seasons s
                LEFT JOIN matches m ON s.id = m.season_id
                GROUP BY s.league_name, s.country
                ORDER BY s.country, s.league_name
            """).fetchall()
            conn.close()
        except Exception:
            return

        if not rows:
            return

        from datetime import datetime

        for row in rows:
            league_name, country, season_count, match_count, latest_unix = row
            if latest_unix:
                latest_date = datetime.fromtimestamp(latest_unix).strftime("%Y-%m-%d")
            else:
                latest_date = "-"
            table.add_row(
                league_name or "-",
                country or "-",
                str(season_count),
                str(match_count),
                latest_date,
            )
