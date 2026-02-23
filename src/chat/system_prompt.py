"""System prompt builder - assembles LLM context from predictions, training report, and data stats."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent


def build_system_prompt(predictions: list[dict] | None = None) -> str:
    """Build a system prompt with current BetBot context.

    Args:
        predictions: Current prediction results (if available).

    Returns:
        System prompt string with relevant context.
    """
    parts = [
        "Du er BetBot-assistenten, en AI-ekspert pa fotball value betting.",
        "Du analyserer kamper, odds, og modellprediksjoner for a hjelpe brukeren.",
        f"Dagens dato: {datetime.now().strftime('%Y-%m-%d')}.",
        "",
    ]

    # Data stats from DB
    data_section = _get_data_stats()
    if data_section:
        parts.append("## Data")
        parts.append(data_section)
        parts.append("")

    # Training report
    training_section = _get_training_stats()
    if training_section:
        parts.append("## Modell")
        parts.append(training_section)
        parts.append("")

    # Current predictions
    if predictions:
        parts.append("## Dagens predictions")
        parts.append(_format_predictions(predictions))
        parts.append("")

    return "\n".join(parts)


def _get_data_stats() -> str | None:
    """Get data statistics from the database."""
    db_path = BASE_DIR / "data" / "processed" / "betbot.db"
    if not db_path.exists():
        return None

    try:
        conn = sqlite3.connect(str(db_path))
        total = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        latest = conn.execute("SELECT MAX(date_unix) FROM matches").fetchone()[0]

        leagues = conn.execute(
            "SELECT COUNT(DISTINCT league_id) FROM matches"
        ).fetchone()[0]

        conn.close()

        if not total:
            return None

        latest_date = datetime.fromtimestamp(latest).strftime("%Y-%m-%d") if latest else "ukjent"
        return f"{total:,} kamper fra {leagues} ligaer. Siste data: {latest_date}."
    except Exception:
        return None


def _get_training_stats() -> str | None:
    """Get model performance from latest training report."""
    report_path = BASE_DIR / "reports" / "latest_training_report.json"
    if not report_path.exists():
        return None

    try:
        with open(report_path) as f:
            report = json.load(f)

        perf = report.get("model_performance", {})
        result = perf.get("result_1x2", {})
        over25 = perf.get("over_25", {})
        btts = perf.get("btts", {})

        lines = []
        if result.get("accuracy") is not None:
            lines.append(f"1X2 accuracy: {result['accuracy']:.1%}")
        if over25.get("accuracy") is not None:
            lines.append(f"Over 2.5 accuracy: {over25['accuracy']:.1%}")
        if btts.get("accuracy") is not None:
            lines.append(f"BTTS accuracy: {btts['accuracy']:.1%}")

        version = report.get("steps", {}).get("save_models", {}).get("model_version")
        if version:
            lines.append(f"Modellversjon: {version}")

        features = report.get("data_stats", {}).get("features_generated")
        if features:
            lines.append(f"Trent pa {features:,} feature-rader")

        return " | ".join(lines) if lines else None
    except Exception:
        return None


def _format_predictions(predictions: list[dict]) -> str:
    """Format predictions for the system prompt."""
    if not predictions:
        return "Ingen value bets funnet."

    lines = [f"Fant {len(predictions)} value bets:"]
    for p in predictions[:20]:  # Limit to 20 for context window
        home = p.get("home_team", "?")
        away = p.get("away_team", "?")
        market = p.get("market", "?")
        edge = p.get("edge")
        edge_str = f"{edge:.1%}" if edge is not None else "?"
        confidence = p.get("confidence", "?")
        kickoff = p.get("kickoff", "")
        league = p.get("league", "")

        lines.append(
            f"- {kickoff} {home} vs {away} ({league}): {market}, edge {edge_str}, {confidence}"
        )

    return "\n".join(lines)
