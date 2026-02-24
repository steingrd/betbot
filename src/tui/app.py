"""BetBot TUI Application - Chat-first single-screen dashboard."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Static
from textual.worker import Worker, WorkerState, get_current_worker

from .tasks import (
    DownloadError,
    DownloadFinished,
    DownloadProgress,
    DownloadResult,
    PredictionError,
    PredictionFinished,
    PredictionProgress,
    TrainingError,
    TrainingFinished,
    TrainingProgress,
    build_download_queue,
    enable_wal_mode,
    run_download_task,
    run_predictions,
    run_training,
)
from .widgets.activity_panel import ActivityPanel
from .widgets.chat_panel import ChatPanel
from .widgets.data_quality_panel import DataQualityPanel
from .widgets.event_log import EventLog

MIN_WIDTH = 116
MIN_HEIGHT = 30


class BetBotApp(App):
    """BetBot TUI - Value bet analysis dashboard."""

    TITLE = "BetBot"
    CSS_PATH = "styles/app.tcss"

    BINDINGS = [
        Binding("escape", "cancel_task", "Avbryt", show=False),
        Binding("ctrl+q", "quit_app", "Avslutt", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._download_worker: Worker | None = None
        self._training_worker: Worker | None = None
        self._prediction_worker: Worker | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-content"):
            yield ChatPanel(id="chat-panel")
            with Vertical(id="right-panel"):
                yield DataQualityPanel(id="data-quality")
                yield ActivityPanel(id="activity-panel")
                yield EventLog(id="event-log", markup=True)
        yield Static(
            "Terminal for liten (minimum 116x30)",
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

    # --- Widget accessors ---

    @property
    def _event_log(self) -> EventLog:
        return self.query_one("#event-log", EventLog)

    @property
    def _activity_panel(self) -> ActivityPanel:
        return self.query_one("#activity-panel", ActivityPanel)

    @property
    def _data_quality(self) -> DataQualityPanel:
        return self.query_one("#data-quality", DataQualityPanel)

    @property
    def _chat_panel(self) -> ChatPanel:
        return self.query_one("#chat-panel", ChatPanel)

    # --- Chat lifecycle ---

    def on_chat_panel_chat_ready(self, _message: ChatPanel.ChatReady) -> None:
        self._chat_panel.show_welcome_message()

    # --- Command routing from ChatPanel ---

    def on_chat_panel_command_requested(self, message: ChatPanel.CommandRequested) -> None:
        if message.command == "download":
            self._start_download()
        elif message.command == "train":
            self._start_training()
        elif message.command == "predict":
            self._start_predictions()
        elif message.command == "results":
            self._show_results()
        elif message.command == "status":
            self._data_quality.refresh_data()
            self._event_log.log_info("Status oppdatert")

    # --- Results ---

    def _show_results(self) -> None:
        """Show recent match results from the database."""
        base_dir = Path(__file__).parent.parent.parent
        db_path = base_dir / "data" / "processed" / "betbot.db"

        if not db_path.exists():
            self._chat_panel.render_system_message("Ingen database funnet. Kjor /download forst.")
            return

        try:
            conn = sqlite3.connect(str(db_path))
            rows = conn.execute("""
                SELECT m.date_unix, s.country, s.league_name,
                       m.home_team, m.home_goals, m.away_goals, m.away_team
                FROM matches m
                LEFT JOIN seasons s ON m.season_id = s.id
                WHERE m.home_shots IS NOT NULL
                ORDER BY m.date_unix DESC
                LIMIT 20
            """).fetchall()
            conn.close()
        except Exception as e:
            self._chat_panel.render_system_message(f"Feil ved henting av resultater: {e}")
            return

        if not rows:
            self._chat_panel.render_system_message("Ingen ferdigspilte kamper funnet.")
            return

        self._chat_panel.render_results_inline(rows)

    # --- Download ---

    def _start_download(self) -> None:
        if self._download_worker is not None and self._download_worker.state == WorkerState.RUNNING:
            self._event_log.log_warning("Nedlasting kjorer allerede - trykk Escape for a avbryte")
            return
        self._event_log.log_info("Starter datanedlasting...")
        self._activity_panel.set_task("Laster ned data...")
        self._download_worker = self._run_download()

    @work(thread=True)
    def _run_download(self) -> None:
        """Background download of all league data."""
        worker = get_current_worker()

        api_key = os.getenv("FOOTYSTATS_API_KEY", "")
        if not api_key or api_key == "example":
            self.post_message(DownloadError("FOOTYSTATS_API_KEY ikke satt i .env"))
            return

        from src.data.data_processor import DataProcessor
        from src.data.footystats_client import FootyStatsClient

        client = FootyStatsClient(api_key=api_key)
        processor = DataProcessor()
        processor.init_database()

        enable_wal_mode(processor.db_path)

        if not client.test_connection():
            self.post_message(DownloadError("Kunne ikke koble til FootyStats API"))
            return

        tasks = build_download_queue(client)
        if not tasks:
            self.post_message(DownloadError("Ingen ligaer funnet - velg ligaer paa FootyStats forst"))
            return

        self.call_from_thread(
            self._event_log.log_info,
            f"Fant {len(tasks)} sesonger a laste ned",
        )

        results: list[DownloadResult] = []

        for i, task in enumerate(tasks):
            if worker.is_cancelled:
                self.call_from_thread(
                    self._event_log.log_warning,
                    f"Nedlasting avbrutt etter {i}/{len(tasks)} sesonger",
                )
                break

            result = run_download_task(task, client, processor)
            results.append(result)

            self.post_message(DownloadProgress(result=result, completed=i + 1, total=len(tasks)))

        self.post_message(DownloadFinished(results=results))

    # --- Training ---

    def _start_training(self) -> None:
        if self._training_worker is not None and self._training_worker.state == WorkerState.RUNNING:
            self._event_log.log_warning("Trening kjorer allerede - trykk Escape for a avbryte")
            return
        self._event_log.log_info("Starter modelltrening...")
        self._activity_panel.set_task("Trener modell...")
        self._training_worker = self._run_training()

    @work(thread=True)
    def _run_training(self) -> None:
        """Background feature engineering + model training."""
        worker = get_current_worker()
        run_training(self, worker)

    # --- Predictions ---

    def _start_predictions(self) -> None:
        if self._prediction_worker is not None and self._prediction_worker.state == WorkerState.RUNNING:
            self._event_log.log_warning("Predictions kjorer allerede - trykk Escape for a avbryte")
            return
        self._event_log.log_info("Starter predictions...")
        self._activity_panel.set_task("Kjorer predictions...")
        self._prediction_worker = self._run_predictions()

    @work(thread=True)
    def _run_predictions(self) -> None:
        """Background prediction pipeline."""
        worker = get_current_worker()
        run_predictions(self, worker)

    # --- Cancel ---

    def action_cancel_task(self) -> None:
        """Cancel the running download, training, or prediction task."""
        cancelled = False
        if self._download_worker is not None and self._download_worker.state == WorkerState.RUNNING:
            self._download_worker.cancel()
            self._event_log.log_warning("Avbryter nedlasting...")
            self._activity_panel.clear_task()
            self._download_worker = None
            cancelled = True
        if self._training_worker is not None and self._training_worker.state == WorkerState.RUNNING:
            self._training_worker.cancel()
            self._event_log.log_warning("Avbryter trening...")
            self._activity_panel.clear_task()
            self._training_worker = None
            cancelled = True
        if self._prediction_worker is not None and self._prediction_worker.state == WorkerState.RUNNING:
            self._prediction_worker.cancel()
            self._event_log.log_warning("Avbryter predictions...")
            self._activity_panel.clear_task()
            self._prediction_worker = None
            cancelled = True
        if not cancelled:
            self._event_log.log_info("Ingen aktiv oppgave a avbryte")

    # --- Message handlers ---

    def on_download_progress(self, message: DownloadProgress) -> None:
        r = message.result
        label = f"{r.task.country} {r.task.league_name} {r.task.year}"
        progress = f"[{message.completed}/{message.total}]"

        if r.error:
            self._event_log.log_error(f"{progress} {label}: {r.error}")
        elif r.match_count == 0:
            self._event_log.log_warning(f"{progress} {label}: ingen kamper")
        else:
            self._event_log.log_success(f"{progress} {label}: {r.match_count} kamper")

        self._activity_panel.set_task(f"Laster ned {label}...")

    def on_download_finished(self, message: DownloadFinished) -> None:
        self._activity_panel.clear_task()
        self._download_worker = None

        total = len(message.results)
        ok = sum(1 for r in message.results if r.ok)
        failed = sum(1 for r in message.results if r.error)
        matches = sum(r.match_count for r in message.results if r.ok)

        summary = f"Nedlasting ferdig: {ok} sesonger, {failed} feil, {matches} kamper lastet ned"
        self._event_log.log_success(
            f"Ferdig: {ok} sesonger, {failed} feil, {matches} kamper"
        )
        self._chat_panel.render_system_message(summary)

        self._data_quality.refresh_data()

    def on_download_error(self, message: DownloadError) -> None:
        self._activity_panel.clear_task()
        self._download_worker = None
        self._event_log.log_error(f"Feil: {message.error}")

    def on_training_progress(self, message: TrainingProgress) -> None:
        self._event_log.log_info(f"[Trening] {message.detail}")
        self._activity_panel.set_task(f"Trener: {message.detail}")

    def on_training_finished(self, message: TrainingFinished) -> None:
        self._activity_panel.clear_task()
        self._training_worker = None
        self._data_quality.refresh_data()

        perf = message.report.get("model_performance", {})
        acc = perf.get("result_1x2", {}).get("accuracy")
        if acc is not None:
            self._event_log.log_success(f"Trening ferdig - 1X2 accuracy: {acc:.1%}")
        else:
            self._event_log.log_success("Trening ferdig")

        self._chat_panel.render_training_report_inline(message.report)

        # Auto-trigger predictions after training
        self._event_log.log_info("Kjorer predictions med ny modell...")
        self._start_predictions()

    def on_training_error(self, message: TrainingError) -> None:
        self._activity_panel.clear_task()
        self._training_worker = None
        self._event_log.log_error(f"Treningsfeil: {message.error}")

    def on_prediction_progress(self, message: PredictionProgress) -> None:
        self._event_log.log_info(f"[Predictions] {message.detail}")
        self._activity_panel.set_task(f"Predictions: {message.detail}")

    def on_prediction_finished(self, message: PredictionFinished) -> None:
        self._activity_panel.clear_task()
        self._prediction_worker = None

        self._chat_panel.render_predictions_inline(message.picks, message.stale_warning)

        if message.picks:
            self._event_log.log_success(
                f"Fant {len(message.picks)} value bets fra {message.match_count} kamper"
            )
            # Auto-trigger LLM analysis
            self._chat_panel.send_auto_analysis(message.picks)
        else:
            self._event_log.log_info(
                f"Ingen value bets funnet ({message.match_count} kamper analysert)"
            )

    def on_prediction_error(self, message: PredictionError) -> None:
        self._activity_panel.clear_task()
        self._prediction_worker = None
        self._event_log.log_error(f"Predictionsfeil: {message.error}")

    # --- Other actions ---

    def action_quit_app(self) -> None:
        self._event_log.log_info("Avslutter BetBot...")
        self._chat_panel.cleanup()
        self.exit()
