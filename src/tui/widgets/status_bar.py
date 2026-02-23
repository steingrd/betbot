"""StatusBar widget - reactive status line at the top of the TUI."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


class StatusBar(Widget):
    """Displays data date, model version, and 1X2 accuracy."""

    DEFAULT_CSS = """
    StatusBar {
        dock: top;
        height: 1;
        background: $accent;
        color: $text;
    }
    StatusBar Static {
        width: 1fr;
        content-align: center middle;
    }
    """

    data_date: reactive[str] = reactive("Ingen data")
    model_version: reactive[str] = reactive("Ingen modell")
    accuracy: reactive[str] = reactive("--")

    def compose(self) -> ComposeResult:
        yield Static(id="status-text")

    def _render_status(self) -> str:
        return f" Data: {self.data_date}  |  Modell: {self.model_version}  |  1X2 acc: {self.accuracy}"

    def watch_data_date(self) -> None:
        self._update_display()

    def watch_model_version(self) -> None:
        self._update_display()

    def watch_accuracy(self) -> None:
        self._update_display()

    def _update_display(self) -> None:
        try:
            self.query_one("#status-text", Static).update(self._render_status())
        except Exception:
            pass

    def on_mount(self) -> None:
        self._load_initial_values()
        self._update_display()

    def _load_initial_values(self) -> None:
        base_dir = Path(__file__).parent.parent.parent.parent

        # Load latest data date from DB
        db_path = base_dir / "data" / "processed" / "betbot.db"
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                row = conn.execute("SELECT MAX(date_unix) FROM matches").fetchone()
                if row and row[0]:
                    self.data_date = datetime.fromtimestamp(row[0]).strftime("%Y-%m-%d")
                conn.close()
            except Exception:
                pass

        # Load model info from training report
        report_path = base_dir / "reports" / "latest_training_report.json"
        if report_path.exists():
            try:
                with open(report_path) as f:
                    report = json.load(f)

                # Model version from save step
                version = report.get("steps", {}).get("save_models", {}).get("model_version")
                if version:
                    self.model_version = f"v{version[:8]}"

                # 1X2 accuracy
                acc = report.get("model_performance", {}).get("result_1x2", {}).get("accuracy")
                if acc is not None:
                    self.accuracy = f"{acc:.1%}"
            except Exception:
                pass
        else:
            # Check if model file exists at all
            model_path = base_dir / "models" / "match_predictor.pkl"
            if model_path.exists():
                mtime = datetime.fromtimestamp(model_path.stat().st_mtime)
                self.model_version = f"v{mtime.strftime('%Y%m%d')}"
