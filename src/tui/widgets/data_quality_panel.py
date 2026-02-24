"""DataQualityPanel widget - compact metrics panel showing data and model status."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static


class DataQualityPanel(Widget):
    """Displays key data and model metrics in a compact vertical list."""

    DEFAULT_CSS = """
    DataQualityPanel {
        height: auto;
        max-height: 12;
        padding: 0 1;
    }
    DataQualityPanel .dq-title {
        text-style: bold;
        margin-bottom: 1;
    }
    DataQualityPanel .dq-metric {
        height: 1;
    }
    DataQualityPanel .dq-metric-dim {
        height: 1;
        color: $text-muted;
    }
    """

    def __init__(
        self,
        db_path: Path | None = None,
        report_path: Path | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        base_dir = Path(__file__).parent.parent.parent.parent
        self._db_path = db_path or base_dir / "data" / "processed" / "betbot.db"
        self._report_path = report_path or base_dir / "reports" / "latest_training_report.json"
        self._model_dir = base_dir / "models"

    def compose(self) -> ComposeResult:
        yield Static("Datakvalitet", classes="dq-title")
        yield Static("", id="dq-data-date", classes="dq-metric-dim")
        yield Static("", id="dq-leagues", classes="dq-metric-dim")
        yield Static("", id="dq-matches", classes="dq-metric-dim")
        yield Static("", id="dq-model", classes="dq-metric-dim")
        yield Static("", id="dq-acc-1x2", classes="dq-metric-dim")
        yield Static("", id="dq-acc-over25", classes="dq-metric-dim")
        yield Static("", id="dq-acc-btts", classes="dq-metric-dim")

    def on_mount(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        """Reload all metrics from database and training report."""
        self._load_db_metrics()
        self._load_model_metrics()

    def _load_db_metrics(self) -> None:
        """Load data metrics from SQLite database."""
        data_date = "-"
        league_count = "-"
        match_count = "-"

        if self._db_path.exists():
            try:
                conn = sqlite3.connect(str(self._db_path))

                # Latest match date
                row = conn.execute("SELECT MAX(date_unix) FROM matches").fetchone()
                if row and row[0]:
                    data_date = datetime.fromtimestamp(row[0]).strftime("%Y-%m-%d")

                # Distinct league count via seasons table
                row = conn.execute(
                    "SELECT COUNT(DISTINCT s.league_name)"
                    " FROM matches m JOIN seasons s ON m.season_id = s.id"
                ).fetchone()
                if row and row[0]:
                    league_count = str(row[0])

                # Total match count
                row = conn.execute("SELECT COUNT(*) FROM matches").fetchone()
                if row and row[0]:
                    match_count = f"{row[0]:,}"

                conn.close()
            except Exception:
                pass

        self._set_metric("dq-data-date", "Siste data", data_date, data_date != "-")
        self._set_metric("dq-leagues", "Ligaer", league_count, league_count != "-")
        self._set_metric("dq-matches", "Kamper", match_count, match_count != "-")

    def _load_model_metrics(self) -> None:
        """Load model metrics from training report JSON."""
        model_version = "Ingen"
        acc_1x2 = "-"
        acc_over25 = "-"
        acc_btts = "-"

        if self._report_path.exists():
            try:
                with open(self._report_path) as f:
                    report = json.load(f)

                # Model version from save step
                version = report.get("steps", {}).get("save_models", {}).get("model_version")
                if version:
                    model_version = f"v{version[:8]}"

                # Model performance
                perf = report.get("model_performance", {})

                acc = perf.get("result_1x2", {}).get("accuracy")
                if acc is not None:
                    acc_1x2 = f"{acc:.1%}"

                acc = perf.get("over_25", {}).get("accuracy")
                if acc is not None:
                    acc_over25 = f"{acc:.1%}"

                acc = perf.get("btts", {}).get("accuracy")
                if acc is not None:
                    acc_btts = f"{acc:.1%}"

            except Exception:
                pass
        else:
            # Check if model file exists without a report
            model_path = self._model_dir / "match_predictor.pkl"
            if model_path.exists():
                mtime = datetime.fromtimestamp(model_path.stat().st_mtime)
                model_version = f"v{mtime.strftime('%Y%m%d')}"

        has_model = model_version != "Ingen"
        self._set_metric("dq-model", "Modell", model_version, has_model)
        self._set_metric("dq-acc-1x2", "1X2 acc", acc_1x2, acc_1x2 != "-")
        self._set_metric("dq-acc-over25", "Over 2.5", acc_over25, acc_over25 != "-")
        self._set_metric("dq-acc-btts", "BTTS", acc_btts, acc_btts != "-")

    def _set_metric(self, widget_id: str, label: str, value: str, has_value: bool) -> None:
        """Update a metric Static widget with label: value formatting."""
        try:
            widget = self.query_one(f"#{widget_id}", Static)
            widget.update(f"  {label}: {value}")
            widget.set_class(not has_value, "dq-metric-dim")
            widget.set_class(has_value, "dq-metric")
        except Exception:
            pass
