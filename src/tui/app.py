"""BetBot TUI Application - Main app with multi-panel layout."""

from __future__ import annotations

import os

from textual import work
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
from .widgets.data_table_view import DataTableView
from .widgets.event_log import EventLog
from .widgets.football_spinner import FootballSpinner
from .widgets.predictions_view import PredictionsView
from .widgets.status_bar import StatusBar
from .widgets.training_view import TrainingView

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
        Binding("escape", "cancel_task", "Avbryt", show=False),
        Binding("ctrl+q", "quit_app", "Avslutt", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._download_worker: Worker | None = None
        self._training_worker: Worker | None = None
        self._prediction_worker: Worker | None = None

    def compose(self) -> ComposeResult:
        yield StatusBar()
        with Horizontal(id="main-content"):
            with Vertical(id="tab-area"):
                with TabbedContent(id="tabs"):
                    with TabPane("Predictions", id="tab-predictions"):
                        yield PredictionsView(id="predictions-view")
                    with TabPane("Data", id="tab-data"):
                        yield DataTableView(id="data-view")
                    with TabPane("Trening", id="tab-training"):
                        yield TrainingView(id="training-view")
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

    # --- Widget accessors ---

    @property
    def _event_log(self) -> EventLog:
        return self.query_one("#event-log", EventLog)

    @property
    def _spinner(self) -> FootballSpinner:
        return self.query_one("#spinner", FootballSpinner)

    @property
    def _status_bar(self) -> StatusBar:
        return self.query_one(StatusBar)

    @property
    def _data_view(self) -> DataTableView:
        return self.query_one("#data-view", DataTableView)

    @property
    def _training_view(self) -> TrainingView:
        return self.query_one("#training-view", TrainingView)

    @property
    def _predictions_view(self) -> PredictionsView:
        return self.query_one("#predictions-view", PredictionsView)

    # --- Download action ---

    def action_download_data(self) -> None:
        if self._download_worker is not None and self._download_worker.state == WorkerState.RUNNING:
            self._event_log.log_warning("Nedlasting kjører allerede - trykk Escape for å avbryte")
            return
        self._event_log.log_info("Starter datanedlasting...")
        self._spinner.active = True
        self._download_worker = self._run_download()

    @work(thread=True)
    def _run_download(self) -> None:
        """Background download of all league data."""
        worker = get_current_worker()

        # Check API key
        api_key = os.getenv("FOOTYSTATS_API_KEY", "")
        if not api_key or api_key == "example":
            self.post_message(DownloadError("FOOTYSTATS_API_KEY ikke satt i .env"))
            return

        # Import data modules (deferred to avoid circular imports at module level)
        from src.data.data_processor import DataProcessor
        from src.data.footystats_client import FootyStatsClient

        client = FootyStatsClient(api_key=api_key)
        processor = DataProcessor()
        processor.init_database()

        # Enable WAL mode for concurrent reads
        enable_wal_mode(processor.db_path)

        # Test connection
        if not client.test_connection():
            self.post_message(DownloadError("Kunne ikke koble til FootyStats API"))
            return

        # Build download queue
        tasks = build_download_queue(client)
        if not tasks:
            self.post_message(DownloadError("Ingen ligaer funnet - velg ligaer på FootyStats først"))
            return

        self.call_from_thread(
            self._event_log.log_info,
            f"Fant {len(tasks)} sesonger å laste ned",
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

    def action_cancel_task(self) -> None:
        """Cancel the running download, training, or prediction task."""
        cancelled = False
        if self._download_worker is not None and self._download_worker.state == WorkerState.RUNNING:
            self._download_worker.cancel()
            self._event_log.log_warning("Avbryter nedlasting...")
            cancelled = True
        if self._training_worker is not None and self._training_worker.state == WorkerState.RUNNING:
            self._training_worker.cancel()
            self._event_log.log_warning("Avbryter trening...")
            self._spinner.active = False
            self._training_worker = None
            cancelled = True
        if self._prediction_worker is not None and self._prediction_worker.state == WorkerState.RUNNING:
            self._prediction_worker.cancel()
            self._event_log.log_warning("Avbryter predictions...")
            self._spinner.active = False
            self._prediction_worker = None
            cancelled = True
        if not cancelled:
            self._event_log.log_info("Ingen aktiv oppgave å avbryte")

    # --- Message handlers ---

    def on_download_progress(self, message: DownloadProgress) -> None:
        r = message.result
        label = f"{r.task.country} {r.task.league_name} {r.task.year}"
        progress = f"[{message.completed}/{message.total}]"

        if r.error:
            self._event_log.log_error(f"{progress} {label}: {r.error}")
        elif r.skipped:
            self._event_log.log_info(f"{progress} {label}: allerede i DB ({r.match_count})")
        elif r.match_count == 0:
            self._event_log.log_warning(f"{progress} {label}: ingen kamper")
        else:
            self._event_log.log_success(f"{progress} {label}: {r.match_count} kamper")

    def on_download_finished(self, message: DownloadFinished) -> None:
        self._spinner.active = False
        self._download_worker = None

        total = len(message.results)
        ok = sum(1 for r in message.results if r.ok and not r.skipped)
        skipped = sum(1 for r in message.results if r.skipped)
        failed = sum(1 for r in message.results if r.error)
        matches = sum(r.match_count for r in message.results if r.ok and not r.skipped)

        self._event_log.log_success(
            f"Ferdig: {ok} nye, {skipped} i DB, {failed} feil, {matches} kamper"
        )

        # Refresh data tab and status bar
        self._data_view.refresh_data()
        self._status_bar._load_initial_values()

    def on_download_error(self, message: DownloadError) -> None:
        self._spinner.active = False
        self._download_worker = None
        self._event_log.log_error(f"Feil: {message.error}")

    # --- Training action ---

    def action_train_model(self) -> None:
        if self._training_worker is not None and self._training_worker.state == WorkerState.RUNNING:
            self._event_log.log_warning("Trening kjører allerede - trykk Escape for å avbryte")
            return
        self._event_log.log_info("Starter modelltrening...")
        self._spinner.active = True
        self._training_view.set_progress("Starter", "Initialiserer...", 0)
        # Switch to training tab
        self.query_one(TabbedContent).active = "tab-training"
        self._training_worker = self._run_training()

    @work(thread=True)
    def _run_training(self) -> None:
        """Background feature engineering + model training."""
        worker = get_current_worker()
        run_training(self, worker)

    def on_training_progress(self, message: TrainingProgress) -> None:
        self._training_view.set_progress(message.step, message.detail, message.percent)
        self._event_log.log_info(f"[Trening] {message.detail}")

    def on_training_finished(self, message: TrainingFinished) -> None:
        self._spinner.active = False
        self._training_worker = None
        self._training_view.show_report(message.report)
        self._status_bar._load_initial_values()

        perf = message.report.get("model_performance", {})
        acc = perf.get("result_1x2", {}).get("accuracy")
        if acc is not None:
            self._event_log.log_success(f"Trening ferdig - 1X2 accuracy: {acc:.1%}")
        else:
            self._event_log.log_success("Trening ferdig")

        # Auto-trigger predictions after training
        self._event_log.log_info("Kjorer predictions med ny modell...")
        self.action_run_predictions()

    def on_training_error(self, message: TrainingError) -> None:
        self._spinner.active = False
        self._training_worker = None
        self._training_view.set_idle()
        self._event_log.log_error(f"Treningsfeil: {message.error}")

    # --- Prediction action ---

    def action_run_predictions(self) -> None:
        if self._prediction_worker is not None and self._prediction_worker.state == WorkerState.RUNNING:
            self._event_log.log_warning("Predictions kjorer allerede - trykk Escape for a avbryte")
            return
        self._event_log.log_info("Starter predictions...")
        self._spinner.active = True
        self.query_one(TabbedContent).active = "tab-predictions"
        self._prediction_worker = self._run_predictions()

    @work(thread=True)
    def _run_predictions(self) -> None:
        """Background prediction pipeline."""
        worker = get_current_worker()
        run_predictions(self, worker)

    def on_prediction_progress(self, message: PredictionProgress) -> None:
        self._event_log.log_info(f"[Predictions] {message.detail}")

    def on_prediction_finished(self, message: PredictionFinished) -> None:
        self._spinner.active = False
        self._prediction_worker = None
        self._predictions_view.show_picks(message.picks, message.stale_warning)

        if message.picks:
            self._event_log.log_success(
                f"Fant {len(message.picks)} value bets fra {message.match_count} kamper"
            )
        else:
            self._event_log.log_info(
                f"Ingen value bets funnet ({message.match_count} kamper analysert)"
            )

    def on_prediction_error(self, message: PredictionError) -> None:
        self._spinner.active = False
        self._prediction_worker = None
        self._event_log.log_error(f"Predictionsfeil: {message.error}")

    # --- Other actions ---

    def action_quit_app(self) -> None:
        self._event_log.log_info("Avslutter BetBot...")
        self.exit()
