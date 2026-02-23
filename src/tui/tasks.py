"""TaskQueue - FIFO task queue with background download/training integration."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import random
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from textual.message import Message


@dataclass
class DownloadTask:
    """A single season download task."""

    season_id: int
    league_id: int
    league_name: str
    country: str
    year: str


@dataclass
class DownloadResult:
    """Result of a single season download."""

    task: DownloadTask
    match_count: int = 0
    skipped: bool = False
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


# --- Textual Messages for thread-safe UI updates ---


class DownloadProgress(Message):
    """Posted from worker thread to update UI on each season."""

    def __init__(self, result: DownloadResult, completed: int, total: int) -> None:
        self.result = result
        self.completed = completed
        self.total = total
        super().__init__()


class DownloadFinished(Message):
    """Posted when the entire download queue is done."""

    def __init__(self, results: list[DownloadResult]) -> None:
        self.results = results
        super().__init__()


class DownloadError(Message):
    """Posted when the download fails fatally (e.g. no API key)."""

    def __init__(self, error: str) -> None:
        self.error = error
        super().__init__()


def stable_league_id(country: str, league_name: str) -> int:
    """Generate a stable league ID from country and league name."""
    key = f"{country}|{league_name}".encode("utf-8")
    return int(hashlib.md5(key).hexdigest()[:8], 16)


def enable_wal_mode(db_path: Path) -> None:
    """Enable WAL mode on SQLite database for concurrent reads."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.close()


def build_download_queue(client) -> list[DownloadTask]:
    """Build a FIFO queue of download tasks from FootyStats leagues.

    Args:
        client: FootyStatsClient instance

    Returns:
        List of DownloadTask in order
    """
    response = client.get_league_list(chosen_leagues_only=True)

    if isinstance(response, dict) and "data" in response:
        leagues = response["data"]
    else:
        leagues = response

    if not leagues:
        return []

    tasks: list[DownloadTask] = []
    league_id_map: dict[tuple[str, str], int] = {}

    for league in leagues:
        league_name = league.get("name", "Unknown")
        country = league.get("country", "")
        seasons = league.get("season", [])

        league_key = (country, league_name)
        if league_key not in league_id_map:
            league_id_map[league_key] = stable_league_id(country, league_name)
        lid = league_id_map[league_key]

        if isinstance(seasons, list):
            for s in seasons:
                tasks.append(
                    DownloadTask(
                        season_id=s["id"],
                        league_id=lid,
                        league_name=league_name,
                        country=country,
                        year=str(s.get("year", "Unknown")),
                    )
                )
        elif seasons:
            tasks.append(
                DownloadTask(
                    season_id=seasons,
                    league_id=lid,
                    league_name=league_name,
                    country=country,
                    year="Current",
                )
            )

    return tasks


def run_download_task(task: DownloadTask, client, processor) -> DownloadResult:
    """Download and process a single season. Returns a DownloadResult.

    This runs in a worker thread - no UI calls here.
    """
    try:
        # Save season metadata
        processor.save_season(
            season_id=task.season_id,
            league_id=task.league_id,
            league_name=task.league_name,
            country=task.country,
            year=task.year,
            season_label=f"{task.country} {task.league_name} {task.year}",
        )

        # Check if already in DB
        existing = processor.load_matches(task.season_id)
        if len(existing) > 0:
            # Update season dates from existing data
            start_date = int(existing["date_unix"].min())
            end_date = int(existing["date_unix"].max())
            processor.update_season_dates(task.season_id, start_date, end_date)
            return DownloadResult(task=task, match_count=len(existing), skipped=True)

        # Download matches
        response = client.get_league_matches(task.season_id)
        if isinstance(response, dict) and "data" in response:
            matches = response["data"]
        else:
            matches = response if isinstance(response, list) else []

        if not matches:
            return DownloadResult(task=task, match_count=0)

        # Process and save
        df = processor.process_matches(matches, task.season_id, league_id=task.league_id)
        processor.save_matches(df)

        # Update season dates
        if len(df) > 0:
            start_date = int(df["date_unix"].min())
            end_date = int(df["date_unix"].max())
            processor.update_season_dates(task.season_id, start_date, end_date)

        return DownloadResult(task=task, match_count=len(matches))

    except Exception as e:
        return DownloadResult(task=task, error=str(e))


# --- Training Messages ---


class TrainingProgress(Message):
    """Posted from worker thread to update UI on training progress."""

    def __init__(self, step: str, detail: str, percent: int | None = None) -> None:
        self.step = step
        self.detail = detail
        self.percent = percent
        super().__init__()


class TrainingFinished(Message):
    """Posted when training is complete."""

    def __init__(self, report: dict) -> None:
        self.report = report
        super().__init__()


class TrainingError(Message):
    """Posted when training fails fatally."""

    def __init__(self, error: str) -> None:
        self.error = error
        super().__init__()


class _ProgressWriter(io.TextIOBase):
    """StringIO replacement that posts TrainingProgress for each line written by print()."""

    def __init__(self, app, step: str):
        self._app = app
        self._step = step
        self._buffer = ""

    def write(self, s: str) -> int:
        self._buffer += s
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()
            if line:
                self._app.post_message(TrainingProgress(step=self._step, detail=line))
        return len(s)

    def flush(self) -> None:
        pass


def run_training(app, worker) -> None:
    """Run feature engineering + model training in a worker thread.

    Args:
        app: The BetBotApp instance (for posting messages and call_from_thread)
        worker: The current worker (for cancellation checks)
    """
    from src.data.data_processor import DataProcessor
    from src.features.feature_engineering import FeatureEngineer
    from src.models.match_predictor import MatchPredictor

    start_time = time.time()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Reproducibility
    random.seed(42)
    np.random.seed(42)

    report = {
        "timestamp": timestamp,
        "random_seed": 42,
        "steps": {},
        "model_performance": {},
        "data_stats": {},
    }

    # Step 1: Load matches
    app.post_message(TrainingProgress(step="Laster data", detail="Laster kamper fra database...", percent=0))

    processor = DataProcessor()
    try:
        matches = processor.load_matches()
    except Exception as e:
        app.post_message(TrainingError(f"Kunne ikke laste data: {e}"))
        return

    if len(matches) == 0:
        app.post_message(TrainingError("Ingen kamper i databasen - last ned data først (Ctrl+D)"))
        return

    step_elapsed = time.time() - start_time
    report["steps"]["load_matches"] = {"duration_seconds": step_elapsed, "matches_loaded": len(matches)}
    report["data_stats"]["total_matches"] = len(matches)

    app.post_message(TrainingProgress(step="Laster data", detail=f"Lastet {len(matches):,} kamper", percent=5))

    if worker.is_cancelled:
        return

    # Step 2: Generate features
    app.post_message(TrainingProgress(step="Features", detail="Genererer features...", percent=5))

    step_start = time.time()
    engineer = FeatureEngineer(matches)
    total_matches = len(matches)

    def feature_progress(current, total):
        pct = 5 + int((current / total) * 70)  # 5-75%
        app.post_message(
            TrainingProgress(step="Features", detail=f"{current:,}/{total:,} kamper", percent=pct)
        )

    features_df = engineer.generate_features(min_matches=3, progress_callback=feature_progress)

    step_elapsed = time.time() - step_start
    report["steps"]["generate_features"] = {
        "duration_seconds": step_elapsed,
        "features_generated": len(features_df),
        "feature_columns": len(features_df.columns),
    }
    report["data_stats"]["features_generated"] = len(features_df)

    app.post_message(
        TrainingProgress(step="Features", detail=f"Genererte {len(features_df):,} feature-rader", percent=75)
    )

    if worker.is_cancelled:
        return

    # Step 3: Check minimum data
    if len(features_df) < 100:
        app.post_message(
            TrainingError(f"For lite data for trening ({len(features_df)} rader, trenger minst 100)")
        )
        return

    # Save features CSV
    output_path = processor.db_path.parent / "features.csv"
    features_df.to_csv(output_path, index=False)

    if worker.is_cancelled:
        return

    # Step 4: Train models (capture stdout from MatchPredictor.train())
    app.post_message(TrainingProgress(step="Trening", detail="Trener ML-modeller...", percent=78))

    step_start = time.time()
    predictor = MatchPredictor()

    progress_writer = _ProgressWriter(app, step="Trening")
    with contextlib.redirect_stdout(progress_writer):
        results = predictor.train(features_df)

    step_elapsed = time.time() - step_start
    report["steps"]["train_models"] = {"duration_seconds": step_elapsed}
    report["model_performance"] = {
        "result_1x2": {
            "accuracy": results["result"]["accuracy"],
            "log_loss": results["result"]["log_loss"],
            "classes": results["result"]["classes"],
        },
        "over_25": {
            "accuracy": results["over25"]["accuracy"],
            "log_loss": results["over25"]["log_loss"],
        },
        "btts": {
            "accuracy": results["btts"]["accuracy"],
            "log_loss": results["btts"]["log_loss"],
        },
    }

    app.post_message(TrainingProgress(step="Trening", detail="Modeller trent", percent=92))

    if worker.is_cancelled:
        return

    # Step 5: Save models
    app.post_message(TrainingProgress(step="Lagrer", detail="Lagrer modeller...", percent=93))

    step_start = time.time()
    model_version = datetime.now().strftime("%Y%m%d_%H%M%S")
    versioned_name = f"match_predictor_{model_version}"

    with contextlib.redirect_stdout(io.StringIO()):  # suppress save prints
        predictor.save()
        predictor.save(versioned_name)

    step_elapsed = time.time() - step_start
    report["steps"]["save_models"] = {
        "duration_seconds": step_elapsed,
        "model_version": model_version,
        "model_path": str(predictor.model_dir / "match_predictor.pkl"),
        "versioned_path": str(predictor.model_dir / f"{versioned_name}.pkl"),
    }

    # Save training report
    base_dir = Path(__file__).parent.parent.parent
    reports_dir = base_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    filename = f"training_report_{timestamp.replace(':', '-').replace(' ', '_')}.json"
    filepath = reports_dir / filename
    with open(filepath, "w") as f:
        json.dump(report, f, indent=2, default=str)

    latest_path = reports_dir / "latest_training_report.json"
    with open(latest_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    total_elapsed = time.time() - start_time
    report["total_duration_seconds"] = total_elapsed

    app.post_message(TrainingProgress(step="Ferdig", detail="Trening fullført", percent=100))
    app.post_message(TrainingFinished(report=report))
