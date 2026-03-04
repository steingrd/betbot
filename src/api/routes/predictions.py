"""Predictions endpoint - returns latest stored predictions."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from ..models import (
    AllPredictions,
    Accumulator,
    ConfidentGoalPick,
    Prediction,
    SafePick,
    StrategySignalResponse,
)

router = APIRouter(prefix="/api/predictions", tags=["predictions"])

BASE_DIR = Path(__file__).parent.parent.parent.parent


def _load_cache() -> dict | list | None:
    """Load raw prediction cache from disk. Returns None on failure."""
    cache_path = BASE_DIR / "data" / "processed" / "latest_predictions.json"
    if not cache_path.exists():
        return None
    try:
        with open(cache_path) as f:
            return json.load(f)
    except Exception:
        return None


def _parse_predictions(picks: list) -> list[Prediction]:
    """Parse a list of raw prediction dicts into Prediction models."""
    result = []
    for p in picks:
        signals = None
        raw_signals = p.get("signals")
        if raw_signals:
            signals = [
                StrategySignalResponse(
                    strategy=s.get("strategy", ""),
                    prob=s.get("prob", 0),
                    edge=s.get("edge", 0),
                    is_value=s.get("is_value", False),
                )
                for s in raw_signals
            ]

        result.append(Prediction(
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
            consensus_count=p.get("consensus_count"),
            total_strategies=p.get("total_strategies"),
            signals=signals,
        ))
    return result


def _parse_safe_picks(items: list) -> list[SafePick]:
    return [SafePick(**p) for p in items]


def _parse_accumulators(items: list) -> list[Accumulator]:
    return [
        Accumulator(
            size=a["size"],
            combined_odds=a["combined_odds"],
            min_prob=a["min_prob"],
            avg_prob=a["avg_prob"],
            picks=_parse_safe_picks(a["picks"]),
        )
        for a in items
    ]


def _parse_confident_goals(items: list) -> list[ConfidentGoalPick]:
    return [ConfidentGoalPick(**p) for p in items]


@router.get("/latest")
def get_latest_predictions() -> list[Prediction]:
    """Return the latest value bet predictions.

    Backwards-compatible: handles both old (list) and new (dict) cache formats.
    """
    raw = _load_cache()
    if raw is None:
        return []

    # New format: dict with value_bets key
    if isinstance(raw, dict):
        return _parse_predictions(raw.get("value_bets", []))

    # Old format: plain list
    return _parse_predictions(raw)


@router.get("/all")
def get_all_predictions() -> AllPredictions:
    """Return all prediction types: value bets, safe picks, accumulators, confident goals."""
    raw = _load_cache()

    if raw is None:
        return AllPredictions(value_bets=[], safe_picks=[], accumulators=[], confident_goals=[])

    # Old format: plain list — only value_bets available
    if isinstance(raw, list):
        return AllPredictions(
            value_bets=_parse_predictions(raw),
            safe_picks=[],
            accumulators=[],
            confident_goals=[],
        )

    return AllPredictions(
        value_bets=_parse_predictions(raw.get("value_bets", [])),
        safe_picks=_parse_safe_picks(raw.get("safe_picks", [])),
        accumulators=_parse_accumulators(raw.get("accumulators", [])),
        confident_goals=_parse_confident_goals(raw.get("confident_goals", [])),
    )
