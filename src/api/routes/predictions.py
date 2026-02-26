"""Predictions endpoint - returns latest stored predictions."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from ..models import Prediction

router = APIRouter(prefix="/api/predictions", tags=["predictions"])

BASE_DIR = Path(__file__).parent.parent.parent.parent


@router.get("/latest")
def get_latest_predictions() -> list[Prediction]:
    """Return the latest predictions if available.

    Predictions are stored in memory by the TaskManager after a predict run.
    As a fallback we also check for a cached file.
    """
    # Try loading from the last prediction cache
    cache_path = BASE_DIR / "data" / "processed" / "latest_predictions.json"
    if not cache_path.exists():
        return []

    try:
        with open(cache_path) as f:
            picks = json.load(f)
    except Exception:
        return []

    return [
        Prediction(
            home_team=p.get("home_team", ""),
            away_team=p.get("away_team", ""),
            league=p.get("league", ""),
            kickoff=p.get("kickoff", ""),
            market=p.get("market", ""),
            model_prob=p.get("model_prob"),
            edge=p.get("edge"),
            confidence=p.get("confidence", ""),
            odds_home=p.get("odds_home"),
            odds_draw=p.get("odds_draw"),
            odds_away=p.get("odds_away"),
        )
        for p in picks
    ]
