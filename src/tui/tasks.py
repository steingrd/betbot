"""TaskQueue - FIFO task queue with background download integration."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

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
