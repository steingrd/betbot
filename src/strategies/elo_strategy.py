"""
Elo rating strategy.

Per-league Elo ratings with Davidson model for three-outcome predictions.
Uses FiveThirtyEight-style goal-difference K-multiplier.

Supports 1X2 only (no Over 2.5 / BTTS).

References:
- Davidson (1970): Paired comparison model with ties
- Hvattum & Arntzen (2010): Elo ratings for football prediction
- FiveThirtyEight: Club Soccer Predictions methodology
"""

import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

from strategies.base import StrategyPredictionError, StrategyTrainingError, TrainingResult


DEFAULT_RATING = 1500
K_FACTOR = 20
HOME_ADVANTAGE = 80
DRAW_NU = 0.85  # Davidson draw parameter
SEASON_REGRESSION = 1 / 3  # Regress 1/3 toward mean between seasons


def _goal_diff_multiplier(goal_diff: int, elo_diff: float) -> float:
    """FiveThirtyEight goal-difference K-multiplier with autocorrelation correction."""
    if goal_diff <= 1:
        base = 1.0
    elif goal_diff == 2:
        base = 1.5
    else:
        base = (11 + goal_diff) / 8.0
    # Autocorrelation correction: prevent over-rewarding heavy favorites
    correction = 2.2 / (abs(elo_diff) * 0.001 + 2.2)
    return base * correction


def _davidson_probs(r_home: float, r_away: float, home_adv: float = HOME_ADVANTAGE,
                    nu: float = DRAW_NU) -> tuple[float, float, float]:
    """Davidson model for three-outcome probabilities.

    Returns (prob_home, prob_draw, prob_away).
    """
    dr = (r_home + home_adv - r_away) / 400.0
    gamma_h = 10 ** (dr / 2)
    gamma_a = 10 ** (-dr / 2)
    denom = gamma_h + gamma_a + nu * math.sqrt(gamma_h * gamma_a)
    p_h = gamma_h / denom
    p_d = nu * math.sqrt(gamma_h * gamma_a) / denom
    p_a = gamma_a / denom
    return p_h, p_d, p_a


class EloStrategy:
    """Elo rating system with Davidson model for 1X2 predictions."""

    @property
    def name(self) -> str:
        return "Elo"

    @property
    def slug(self) -> str:
        return "elo"

    @property
    def supported_markets(self) -> list[str]:
        return ["H", "D", "A"]

    def __init__(self) -> None:
        # league_name -> {team_name: rating}
        self._ratings: dict[str, dict[str, float]] = {}
        # league_name -> {team_name: games_played}
        self._games_played: dict[str, dict[str, int]] = {}
        self._fitted = False

    def train(
        self, matches_df: pd.DataFrame, features_df: pd.DataFrame
    ) -> TrainingResult:
        """Compute Elo ratings by replaying all matches chronologically.

        Args:
            matches_df: Raw match data with home_team, away_team, home_goals,
                        away_goals, date_unix, league_name, season_id.
            features_df: Unused.
        """
        start = time.monotonic()

        required = {"home_team", "away_team", "home_goals", "away_goals", "date_unix", "league_name"}
        missing = required - set(matches_df.columns)
        if missing:
            raise StrategyTrainingError(self.slug, f"Missing columns: {missing}")

        df = matches_df.dropna(subset=list(required)).copy()
        df = df.sort_values("date_unix")

        self._ratings = {}
        self._games_played = {}

        # Track season transitions for regression
        prev_season: dict[str, int | None] = {}  # league -> last season_id

        for _, row in df.iterrows():
            league = row["league_name"]
            home = row["home_team"]
            away = row["away_team"]
            hg = int(row["home_goals"])
            ag = int(row["away_goals"])
            season_id = row.get("season_id")

            # Initialize league if new
            if league not in self._ratings:
                self._ratings[league] = {}
                self._games_played[league] = {}
                prev_season[league] = None

            ratings = self._ratings[league]
            games = self._games_played[league]

            # Season regression
            if season_id is not None and prev_season[league] is not None and season_id != prev_season[league]:
                league_mean = np.mean(list(ratings.values())) if ratings else DEFAULT_RATING
                for team in ratings:
                    ratings[team] = ratings[team] + SEASON_REGRESSION * (league_mean - ratings[team])
                # Reset games played for cold-start K doubling
                for team in games:
                    games[team] = max(games[team] - 10, 0)
            prev_season[league] = season_id

            # Initialize teams
            if home not in ratings:
                league_mean = np.mean(list(ratings.values())) if ratings else DEFAULT_RATING
                ratings[home] = league_mean - 100  # cold start: below average
                games[home] = 0
            if away not in ratings:
                league_mean = np.mean(list(ratings.values())) if ratings else DEFAULT_RATING
                ratings[away] = league_mean - 100
                games[away] = 0

            r_home = ratings[home]
            r_away = ratings[away]

            # Expected score (home perspective)
            e_home = 1.0 / (1.0 + 10 ** ((r_away - r_home - HOME_ADVANTAGE) / 400.0))

            # Actual score
            if hg > ag:
                s_home = 1.0
            elif hg == ag:
                s_home = 0.5
            else:
                s_home = 0.0

            # K-factor with goal-diff multiplier and cold-start doubling
            goal_diff = abs(hg - ag)
            elo_diff = r_home + HOME_ADVANTAGE - r_away
            mult = _goal_diff_multiplier(goal_diff, elo_diff)

            k_home = K_FACTOR * mult * (2.0 if games[home] < 10 else 1.0)
            k_away = K_FACTOR * mult * (2.0 if games[away] < 10 else 1.0)

            # Update ratings
            ratings[home] += k_home * (s_home - e_home)
            ratings[away] += k_away * ((1.0 - s_home) - (1.0 - e_home))

            games[home] = games.get(home, 0) + 1
            games[away] = games.get(away, 0) + 1

        self._fitted = True
        duration = time.monotonic() - start

        return TrainingResult(
            accuracy={"result": None},
            log_loss={"result": None},
            num_samples=len(df),
            duration_seconds=round(duration, 2),
            metadata={
                "leagues": str(len(self._ratings)),
                "total_teams": str(sum(len(r) for r in self._ratings.values())),
            },
        )

    def predict(
        self, matches_df: pd.DataFrame, features_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Predict 1X2 probabilities using Davidson model.

        Returns DataFrame with match_id, prob_H, prob_D, prob_A, prob_over25, prob_btts.
        O2.5 and BTTS are NaN (not supported by Elo).
        """
        if not self._fitted:
            raise StrategyPredictionError(self.slug, "Model not fitted")

        source = features_df if "league_name" in features_df.columns else matches_df

        results = []
        for _, row in source.iterrows():
            match_id = row.get("match_id", row.get("id"))
            home = row["home_team"]
            away = row["away_team"]
            league = row.get("league_name")

            probs = self._predict_match(home, away, league)
            results.append({
                "match_id": match_id,
                "prob_H": probs[0],
                "prob_D": probs[1],
                "prob_A": probs[2],
                "prob_over25": float("nan"),
                "prob_btts": float("nan"),
            })

        return pd.DataFrame(results)

    def _predict_match(self, home: str, away: str, league: str | None) -> tuple[float, float, float]:
        """Predict a single match. Returns (H, D, A)."""
        ratings = self._ratings.get(league) if league else None

        if ratings is None:
            return (float("nan"), float("nan"), float("nan"))

        r_home = ratings.get(home, DEFAULT_RATING)
        r_away = ratings.get(away, DEFAULT_RATING)

        return _davidson_probs(r_home, r_away)

    def save(self, path: Path) -> None:
        """Save ratings as JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "ratings": self._ratings,
            "games_played": self._games_played,
        }
        path.write_text(json.dumps(data, indent=2))

    def load(self, path: Path) -> bool:
        """Load ratings from JSON."""
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text())
            self._ratings = data["ratings"]
            self._games_played = data.get("games_played", {})
            self._fitted = bool(self._ratings)
            return True
        except Exception:
            return False

    @property
    def is_fitted(self) -> bool:
        return self._fitted
