"""Data status and results endpoints."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Query

from ..models import DataStatus, MatchResult

router = APIRouter(prefix="/api/data", tags=["data"])

BASE_DIR = Path(__file__).parent.parent.parent.parent
DB_PATH = BASE_DIR / "data" / "processed" / "betbot.db"
REPORT_PATH = BASE_DIR / "reports" / "latest_training_report.json"
MODEL_DIR = BASE_DIR / "models"


@router.get("/status")
def get_data_status() -> DataStatus:
    total_matches = 0
    league_count = 0
    latest_date = None

    if DB_PATH.exists():
        conn = sqlite3.connect(str(DB_PATH))
        try:
            row = conn.execute("SELECT COUNT(*) FROM matches").fetchone()
            total_matches = row[0] if row else 0

            row = conn.execute("SELECT MAX(date_unix) FROM matches").fetchone()
            if row and row[0]:
                latest_date = datetime.fromtimestamp(row[0]).strftime("%Y-%m-%d")

            row = conn.execute(
                "SELECT COUNT(DISTINCT s.league_name)"
                " FROM matches m JOIN seasons s ON m.season_id = s.id"
            ).fetchone()
            league_count = row[0] if row and row[0] else 0
        finally:
            conn.close()

    # Model metrics from training report
    model_version = None
    acc_1x2 = None
    acc_over25 = None
    acc_btts = None

    if REPORT_PATH.exists():
        try:
            with open(REPORT_PATH) as f:
                report = json.load(f)

            version = report.get("steps", {}).get("save_models", {}).get("model_version")
            if version:
                model_version = version

            perf = report.get("model_performance", {})
            acc_1x2 = perf.get("result_1x2", {}).get("accuracy")
            acc_over25 = perf.get("over_25", {}).get("accuracy")
            acc_btts = perf.get("btts", {}).get("accuracy")
        except Exception:
            pass
    elif not model_version:
        model_path = MODEL_DIR / "match_predictor.pkl"
        if model_path.exists():
            mtime = datetime.fromtimestamp(model_path.stat().st_mtime)
            model_version = mtime.strftime("%Y%m%d_%H%M%S")

    return DataStatus(
        total_matches=total_matches,
        league_count=league_count,
        latest_date=latest_date,
        model_version=model_version,
        acc_1x2=acc_1x2,
        acc_over25=acc_over25,
        acc_btts=acc_btts,
    )


@router.get("/results")
def get_results(limit: int = Query(default=20, le=100)) -> list[MatchResult]:
    if not DB_PATH.exists():
        return []

    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            """
            SELECT m.date_unix, s.country, s.league_name,
                   m.home_team, m.home_goals, m.away_goals, m.away_team
            FROM matches m
            LEFT JOIN seasons s ON m.season_id = s.id
            WHERE m.home_goals IS NOT NULL
            ORDER BY m.date_unix DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    results = []
    for row in rows:
        date_str = datetime.fromtimestamp(row[0]).strftime("%Y-%m-%d") if row[0] else ""
        results.append(
            MatchResult(
                date=date_str,
                country=row[1],
                league=row[2],
                home_team=row[3],
                home_goals=row[4] or 0,
                away_goals=row[5] or 0,
                away_team=row[6],
            )
        )
    return results
