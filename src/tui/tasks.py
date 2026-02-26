"""TaskQueue - FIFO task queue with background download/training integration.

Business logic functions (run_download, run_training, run_predictions) use
generic callbacks so they can be driven by both the TUI (Textual) and the
Web API (FastAPI).  The Textual Message subclasses are kept for TUI
compatibility and also serve as plain dataclasses for the API layer.
"""

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
from typing import Any, Callable, Optional, Protocol

import numpy as np
import pandas as pd
from textual.message import Message


# --- Callback protocol ---

ProgressCallback = Callable[[Any], None]
"""Signature: on_progress(event) where event is one of the Message dataclasses below."""

CancelledCheck = Callable[[], bool]
"""Signature: is_cancelled() -> bool"""


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
# These also serve as plain event objects for the API layer.


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


# Grace period: treat seasons as active if last match was < 30 days ago
_GRACE_PERIOD_SECONDS = 30 * 86400


def filter_download_queue(
    tasks: list[DownloadTask], processor, now: float | None = None
) -> tuple[list[DownloadTask], list[DownloadTask]]:
    """Filter download queue to skip finished seasons already in DB.

    Returns:
        Tuple of (tasks_to_download, tasks_skipped)
    """
    if now is None:
        now = time.time()

    conn = sqlite3.connect(str(processor.db_path))
    rows = conn.execute(
        """
        SELECT s.id, s.end_date, COUNT(m.id) as match_count
        FROM seasons s
        LEFT JOIN matches m ON s.id = m.season_id
        GROUP BY s.id
        """
    ).fetchall()
    conn.close()

    known: dict[int, tuple[int | None, int]] = {}
    for season_id, end_date, match_count in rows:
        known[season_id] = (end_date, match_count)

    to_download: list[DownloadTask] = []
    skipped: list[DownloadTask] = []

    for task in tasks:
        if task.season_id not in known:
            to_download.append(task)
        elif known[task.season_id][1] == 0:
            # Season metadata exists but no matches — need to download
            to_download.append(task)
        elif known[task.season_id][0] is None:
            # No end date known — treat as active
            to_download.append(task)
        elif known[task.season_id][0] + _GRACE_PERIOD_SECONDS > now:
            # Active or recently ended — still download
            to_download.append(task)
        else:
            # Finished season with data in DB — skip
            skipped.append(task)

    return to_download, skipped


def _is_active_season(processor, season_id: int) -> bool:
    """Check if a season is still active (end_date in the future or NULL)."""
    import sqlite3

    conn = sqlite3.connect(str(processor.db_path))
    row = conn.execute(
        "SELECT end_date FROM seasons WHERE id = ?", (season_id,)
    ).fetchone()
    conn.close()

    if row is None or row[0] is None:
        return True  # Unknown or no end date -> treat as active
    return row[0] > time.time()


def run_download_task(task: DownloadTask, client, processor) -> DownloadResult:
    """Download and process a single season. Returns a DownloadResult.

    This runs in a worker thread - no UI calls here.
    Uses upsert so existing matches get updated with new results.
    Bypasses cache for active seasons to pick up completed matches.
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

        # For active seasons, bypass cache to get fresh data
        active = _is_active_season(processor, task.season_id)
        use_cache = not active

        # Download matches
        response = client.get_league_matches(task.season_id, use_cache=use_cache)
        if isinstance(response, dict) and "data" in response:
            matches = response["data"]
        else:
            matches = response if isinstance(response, list) else []

        if not matches:
            return DownloadResult(task=task, match_count=0)

        # Remove any previously saved incomplete matches for this season
        processor.delete_incomplete_matches(season_id=task.season_id)

        # Process and save (upsert updates existing matches)
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


# --- Prediction Messages ---


class PredictionProgress(Message):
    """Posted from worker thread to update UI on prediction progress."""

    def __init__(self, step: str, detail: str) -> None:
        self.step = step
        self.detail = detail
        super().__init__()


class PredictionFinished(Message):
    """Posted when predictions are complete."""

    def __init__(self, picks: list, match_count: int, stale_warning: str | None = None) -> None:
        self.picks = picks
        self.match_count = match_count
        self.stale_warning = stale_warning
        super().__init__()


class PredictionError(Message):
    """Posted when predictions fail fatally."""

    def __init__(self, error: str) -> None:
        self.error = error
        super().__init__()


def run_predictions(on_progress: ProgressCallback, is_cancelled: CancelledCheck) -> None:
    """Run prediction pipeline.

    Loads model, fetches NT matches, computes features, predicts, finds value bets.
    Uses generic callbacks so it can be driven by TUI or API.
    """
    on_progress(PredictionProgress(step="Laster modell", detail="Laster ML-modell og historisk data..."))

    try:
        from src.predictions.daily_picks import DailyPicksFinder

        finder = DailyPicksFinder()
        finder.load_model()
    except Exception as e:
        on_progress(PredictionError(f"Kunne ikke laste modell: {e}"))
        return

    match_count = len(finder.matches_df) if finder.matches_df is not None else 0
    on_progress(PredictionProgress(step="Laster modell", detail=f"Modell lastet ({match_count:,} kamper)"))

    if is_cancelled():
        return

    # Check for stale data
    stale_warning = None
    if finder.matches_df is not None and len(finder.matches_df) > 0:
        latest_unix = finder.matches_df["date_unix"].max()
        days_old = (time.time() - latest_unix) / 86400
        if days_old > 30:
            stale_warning = f"Data er {int(days_old)} dager gammel - kjor /download for a oppdatere"

    # Fetch upcoming matches from Norsk Tipping
    on_progress(PredictionProgress(step="Henter kamper", detail="Henter kamper fra Norsk Tipping..."))

    try:
        matches = finder.get_upcoming_matches()
    except Exception as e:
        on_progress(PredictionError(f"Kunne ikke hente kamper: {e}"))
        return

    if not matches:
        on_progress(PredictionFinished(picks=[], match_count=0, stale_warning=stale_warning))
        return

    on_progress(
        PredictionProgress(step="Henter kamper", detail=f"Fant {len(matches)} kamper fra Norsk Tipping")
    )

    if is_cancelled():
        return

    # Find value bets
    on_progress(PredictionProgress(step="Analyserer", detail=f"Analyserer {len(matches)} kamper..."))

    try:
        picks = finder.find_value_bets(matches)
    except Exception as e:
        on_progress(PredictionError(f"Feil under analyse: {e}"))
        return

    on_progress(PredictionFinished(picks=picks, match_count=len(matches), stale_warning=stale_warning))


class _ProgressWriter(io.TextIOBase):
    """StringIO replacement that posts TrainingProgress for each line written by print()."""

    def __init__(self, on_progress: ProgressCallback, step: str):
        self._on_progress = on_progress
        self._step = step
        self._buffer = ""

    def write(self, s: str) -> int:
        self._buffer += s
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()
            if line:
                self._on_progress(TrainingProgress(step=self._step, detail=line))
        return len(s)

    def flush(self) -> None:
        pass


def run_training(on_progress: ProgressCallback, is_cancelled: CancelledCheck) -> None:
    """Run feature engineering + model training.

    Uses generic callbacks so it can be driven by TUI or API.
    """
    from src.data.data_processor import DataProcessor
    from src.features.cache_metadata import (
        compute_source_fingerprint,
        read_cache_metadata,
        validate_cache_metadata,
        write_cache_metadata,
    )
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
    on_progress(TrainingProgress(step="Laster data", detail="Laster kamper fra database...", percent=0))

    processor = DataProcessor()
    try:
        matches = processor.load_matches()
    except Exception as e:
        on_progress(TrainingError(f"Kunne ikke laste data: {e}"))
        return

    if len(matches) == 0:
        on_progress(TrainingError("Ingen kamper i databasen - last ned data forst (/download)"))
        return

    step_elapsed = time.time() - start_time
    report["steps"]["load_matches"] = {"duration_seconds": step_elapsed, "matches_loaded": len(matches)}
    report["data_stats"]["total_matches"] = len(matches)

    on_progress(TrainingProgress(step="Laster data", detail=f"Lastet {len(matches):,} kamper", percent=5))

    if is_cancelled():
        return

    # Step 2: Generate features (incremental - reuse cached features)
    on_progress(TrainingProgress(step="Features", detail="Genererer features...", percent=5))

    step_start = time.time()

    # Load cached features to skip already-computed matches
    features_path = processor.db_path.parent / "features.csv"
    metadata_path = features_path.with_suffix(".meta.json")
    cached_df = None
    skip_ids = None
    source_fingerprint = compute_source_fingerprint(matches)
    if features_path.exists():
        try:
            metadata = read_cache_metadata(metadata_path)
            cache_ok, reason = validate_cache_metadata(
                metadata,
                feature_version=FeatureEngineer.FEATURE_VERSION,
                source_fingerprint=source_fingerprint,
            )
            if cache_ok:
                cached_df = pd.read_csv(features_path)
                # Validate that cached features have the expected columns
                expected_cols = set(MatchPredictor.FEATURE_COLS)
                if expected_cols.issubset(set(cached_df.columns)):
                    skip_ids = set(cached_df["match_id"].tolist())
                    new_match_count = len(matches) - len(skip_ids & set(matches["id"].tolist()))
                    on_progress(
                        TrainingProgress(
                            step="Features",
                            detail=f"Cache: {len(skip_ids):,} kamper, {new_match_count:,} nye",
                            percent=7,
                        )
                    )
                else:
                    cached_df = None  # Column mismatch - regenerate all
            else:
                on_progress(
                    TrainingProgress(
                        step="Features",
                        detail=f"Cache invalidert ({reason})",
                        percent=7,
                    )
                )
        except Exception:
            cached_df = None

    engineer = FeatureEngineer(matches)

    def feature_progress(current, total):
        pct = 5 + int((current / total) * 70)  # 5-75%
        on_progress(
            TrainingProgress(step="Features", detail=f"{current:,}/{total:,} kamper", percent=pct)
        )

    new_features_df = engineer.generate_features(
        min_matches=3, progress_callback=feature_progress, skip_match_ids=skip_ids
    )

    # Combine cached + new features
    if cached_df is not None and len(new_features_df) > 0:
        features_df = pd.concat([cached_df, new_features_df], ignore_index=True)
        # Remove any duplicates (shouldn't happen, but safety net)
        features_df = features_df.drop_duplicates(subset=["match_id"], keep="last")
    elif cached_df is not None and len(new_features_df) == 0:
        features_df = cached_df
    else:
        features_df = new_features_df

    step_elapsed = time.time() - step_start
    report["steps"]["generate_features"] = {
        "duration_seconds": step_elapsed,
        "features_generated": len(features_df),
        "feature_columns": len(features_df.columns),
        "cached_features": len(cached_df) if cached_df is not None else 0,
        "new_features": len(new_features_df),
    }
    report["data_stats"]["features_generated"] = len(features_df)

    on_progress(
        TrainingProgress(step="Features", detail=f"Genererte {len(features_df):,} feature-rader ({len(new_features_df):,} nye)", percent=75)
    )

    if is_cancelled():
        return

    # Step 3: Check minimum data
    if len(features_df) < 100:
        on_progress(
            TrainingError(f"For lite data for trening ({len(features_df)} rader, trenger minst 100)")
        )
        return

    # Save features CSV + metadata
    output_path = processor.db_path.parent / "features.csv"
    features_df.to_csv(output_path, index=False)
    write_cache_metadata(
        output_path.with_suffix(".meta.json"),
        feature_version=FeatureEngineer.FEATURE_VERSION,
        source_fingerprint=source_fingerprint,
        match_count=len(matches),
    )

    if is_cancelled():
        return

    # Step 4: Train models (capture stdout from MatchPredictor.train())
    on_progress(TrainingProgress(step="Trening", detail="Trener ML-modeller...", percent=78))

    step_start = time.time()
    predictor = MatchPredictor()

    progress_writer = _ProgressWriter(on_progress, step="Trening")
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

    on_progress(TrainingProgress(step="Trening", detail="Modeller trent", percent=92))

    if is_cancelled():
        return

    # Step 5: Save models
    on_progress(TrainingProgress(step="Lagrer", detail="Lagrer modeller...", percent=93))

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

    on_progress(TrainingProgress(step="Ferdig", detail="Trening fullfort", percent=100))
    on_progress(TrainingFinished(report=report))


def run_download(
    on_progress: ProgressCallback,
    is_cancelled: CancelledCheck,
    full: bool = False,
) -> None:
    """Run download pipeline. Uses generic callbacks.

    Downloads league data from FootyStats, skipping finished seasons unless full=True.
    """
    import os

    api_key = os.getenv("FOOTYSTATS_API_KEY", "")
    if not api_key or api_key == "example":
        on_progress(DownloadError("FOOTYSTATS_API_KEY ikke satt i .env"))
        return

    from src.data.data_processor import DataProcessor
    from src.data.footystats_client import FootyStatsClient

    client = FootyStatsClient(api_key=api_key)
    processor = DataProcessor()
    processor.init_database()
    enable_wal_mode(processor.db_path)

    if not client.test_connection():
        on_progress(DownloadError("Kunne ikke koble til FootyStats API"))
        return

    tasks = build_download_queue(client)
    if not tasks:
        on_progress(DownloadError("Ingen ligaer funnet - velg ligaer paa FootyStats forst"))
        return

    # Filter out finished seasons unless full download requested
    skipped_results: list[DownloadResult] = []
    if not full:
        tasks, skipped_tasks = filter_download_queue(tasks, processor)
        skipped_results = [DownloadResult(task=t, skipped=True) for t in skipped_tasks]

    if not tasks:
        on_progress(DownloadFinished(results=skipped_results))
        return

    results: list[DownloadResult] = list(skipped_results)

    for i, task in enumerate(tasks):
        if is_cancelled():
            break

        result = run_download_task(task, client, processor)
        results.append(result)

        on_progress(DownloadProgress(result=result, completed=i + 1, total=len(tasks)))

    on_progress(DownloadFinished(results=results))
