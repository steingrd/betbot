"""TrainingView widget - shows training progress, report, or empty state."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import ProgressBar, Static


def _fmt_duration(seconds: float) -> str:
    """Format seconds as human-readable duration."""
    s = int(seconds)
    if s >= 3600:
        return f"{s // 3600}h {(s % 3600) // 60}m {s % 60}s"
    if s >= 60:
        return f"{s // 60}m {s % 60}s"
    return f"{s}s"


class TrainingView(Widget):
    """Training tab content: empty state, progress, or report."""

    DEFAULT_CSS = """
    TrainingView {
        height: 100%;
        width: 100%;
    }
    TrainingView .training-empty {
        width: 100%;
        height: 100%;
        content-align: center middle;
        color: $text-muted;
    }
    TrainingView .training-progress-area {
        width: 100%;
        padding: 1 2;
    }
    TrainingView .training-step {
        width: 100%;
        margin-bottom: 1;
    }
    TrainingView .training-detail {
        width: 100%;
        color: $text-muted;
        margin-bottom: 1;
    }
    TrainingView ProgressBar {
        width: 100%;
        margin-bottom: 1;
    }
    TrainingView .training-report {
        width: 100%;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(
            "Ingen treningsresultater\n\nTrykk Ctrl+T for å trene modellen",
            id="training-empty",
            classes="training-empty",
        )
        with Widget(id="training-progress-area", classes="training-progress-area"):
            yield Static("", id="training-step", classes="training-step")
            yield Static("", id="training-detail", classes="training-detail")
            yield ProgressBar(id="training-bar", total=100, show_eta=False)
        yield Static("", id="training-report", classes="training-report")

    def on_mount(self) -> None:
        self.set_idle()

    def set_idle(self) -> None:
        """Show empty state."""
        self.query_one("#training-empty").display = True
        self.query_one("#training-progress-area").display = False
        self.query_one("#training-report").display = False

    def set_progress(self, step: str, detail: str, percent: int | None) -> None:
        """Update progress display."""
        self.query_one("#training-empty").display = False
        self.query_one("#training-progress-area").display = True
        self.query_one("#training-report").display = False

        self.query_one("#training-step", Static).update(f"[bold]{step}[/bold]")
        self.query_one("#training-detail", Static).update(detail)

        bar = self.query_one("#training-bar", ProgressBar)
        if percent is not None:
            bar.update(progress=percent)
        bar.display = percent is not None

    def show_report(self, report: dict) -> None:
        """Render training report."""
        self.query_one("#training-empty").display = False
        self.query_one("#training-progress-area").display = False
        self.query_one("#training-report").display = True

        lines = []
        lines.append("[bold]Treningsrapport[/bold]")
        lines.append("")

        # Timing
        total = report.get("total_duration_seconds", 0)
        lines.append(f"  Tid: {_fmt_duration(total)}")
        lines.append(f"  Tidspunkt: {report.get('timestamp', '-')}")
        lines.append("")

        # Data stats
        stats = report.get("data_stats", {})
        lines.append("[bold]Data[/bold]")
        lines.append(f"  Kamper lastet: {stats.get('total_matches', 0):,}")
        lines.append(f"  Feature-rader: {stats.get('features_generated', 0):,}")
        lines.append("")

        # Model performance
        perf = report.get("model_performance", {})
        lines.append("[bold]Modellresultater (out-of-sample)[/bold]")

        r1x2 = perf.get("result_1x2", {})
        acc = r1x2.get("accuracy")
        ll = r1x2.get("log_loss")
        if acc is not None:
            lines.append(f"  1X2:      {acc:.1%} accuracy, {ll:.3f} log loss")
        else:
            lines.append("  1X2:      (ingen intern validering)")

        o25 = perf.get("over_25", {})
        acc = o25.get("accuracy")
        ll = o25.get("log_loss")
        if acc is not None:
            lines.append(f"  Over 2.5: {acc:.1%} accuracy, {ll:.3f} log loss")
        else:
            lines.append("  Over 2.5: (ingen intern validering)")

        btts = perf.get("btts", {})
        acc = btts.get("accuracy")
        ll = btts.get("log_loss")
        if acc is not None:
            lines.append(f"  BTTS:     {acc:.1%} accuracy, {ll:.3f} log loss")
        else:
            lines.append("  BTTS:     (ingen intern validering)")

        lines.append("")

        # Model version
        save_info = report.get("steps", {}).get("save_models", {})
        version = save_info.get("model_version", "-")
        lines.append(f"  Modellversjon: {version}")

        # Step durations
        steps = report.get("steps", {})
        lines.append("")
        lines.append("[bold]Steg-tider[/bold]")
        step_labels = {
            "load_matches": "Last data",
            "generate_features": "Features",
            "train_models": "Trening",
            "save_models": "Lagring",
        }
        for key, label in step_labels.items():
            dur = steps.get(key, {}).get("duration_seconds")
            if dur is not None:
                lines.append(f"  {label}: {_fmt_duration(dur)}")

        self.query_one("#training-report", Static).update("\n".join(lines))
