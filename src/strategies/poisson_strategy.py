"""
Poisson / Dixon-Coles strategy.

Classical statistical model for football prediction, fitted per-league.

References:
- Dixon & Coles (1997): "Modelling Association Football Scores and Inefficiencies in the Football Betting Market"
- opisthokonta.net sum-to-zero trick for faster optimization
- dashee87.github.io Python tutorial
"""

import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln
from scipy.stats import poisson

from strategies.base import StrategyPredictionError, StrategyTrainingError, TrainingResult


# Maximum goals in the goal matrix (8x8 = 0..7)
MAX_GOALS = 7


def _tau(x: int, y: int, lam: float, mu: float, rho: float) -> float:
    """Dixon-Coles correction for low-scoring outcomes."""
    if x == 0 and y == 0:
        return 1.0 - lam * mu * rho
    elif x == 0 and y == 1:
        return 1.0 + lam * rho
    elif x == 1 and y == 0:
        return 1.0 + mu * rho
    elif x == 1 and y == 1:
        return 1.0 - rho
    return 1.0


def _dc_log_likelihood(params: np.ndarray, teams: list[str], home_goals: np.ndarray,
                        away_goals: np.ndarray, home_idx: np.ndarray, away_idx: np.ndarray,
                        weights: np.ndarray) -> float:
    """Negative log-likelihood for Dixon-Coles model.

    Parameter layout (sum-to-zero trick on defense):
        params[0 : n_teams]       = attack strengths (alpha)
        params[n_teams : 2*n_teams - 1] = defense strengths (beta), last is -sum(rest)
        params[-2]                = home advantage (gamma)
        params[-1]                = rho (low-score correlation)
    """
    n = len(teams)

    attack = params[:n]
    # Sum-to-zero: last defense param = -sum(others)
    beta_free = params[n:2 * n - 1]
    beta_last = -np.sum(beta_free)
    defense = np.concatenate([beta_free, [beta_last]])

    gamma = params[-2]
    rho = params[-1]

    # Expected goals
    lam = np.exp(attack[home_idx] + defense[away_idx] + gamma)  # home expected
    mu = np.exp(attack[away_idx] + defense[home_idx])  # away expected

    # Vectorized log-likelihood
    log_pmf_home = home_goals * np.log(lam) - lam - gammaln(home_goals + 1)
    log_pmf_away = away_goals * np.log(mu) - mu - gammaln(away_goals + 1)

    # Vectorized tau correction (only affects 0-0, 0-1, 1-0, 1-1)
    tau_vals = np.ones(len(home_goals))
    m00 = (home_goals == 0) & (away_goals == 0)
    m01 = (home_goals == 0) & (away_goals == 1)
    m10 = (home_goals == 1) & (away_goals == 0)
    m11 = (home_goals == 1) & (away_goals == 1)
    tau_vals[m00] = 1.0 - lam[m00] * mu[m00] * rho
    tau_vals[m01] = 1.0 + lam[m01] * rho
    tau_vals[m10] = 1.0 + mu[m10] * rho
    tau_vals[m11] = 1.0 - rho
    tau_vals = np.maximum(tau_vals, 1e-10)

    ll = np.sum(weights * (log_pmf_home + log_pmf_away + np.log(tau_vals)))
    return -ll  # minimize negative log-likelihood


def _goal_matrix(lam: float, mu: float, rho: float) -> np.ndarray:
    """Build (MAX_GOALS+1) x (MAX_GOALS+1) probability matrix with Dixon-Coles correction."""
    n = MAX_GOALS + 1
    matrix = np.zeros((n, n))

    for i in range(n):
        for j in range(n):
            prob = poisson.pmf(i, lam) * poisson.pmf(j, mu) * _tau(i, j, lam, mu, rho)
            matrix[i, j] = max(prob, 0.0)

    # Normalize
    total = matrix.sum()
    if total > 0:
        matrix /= total

    return matrix


class PoissonStrategy:
    """Dixon-Coles model fitted per-league."""

    @property
    def name(self) -> str:
        return "Poisson"

    @property
    def slug(self) -> str:
        return "poisson"

    @property
    def supported_markets(self) -> list[str]:
        return ["H", "D", "A", "Over 2.5", "BTTS"]

    def __init__(self, xi: float = 0.001) -> None:
        self._xi = xi  # time decay rate (per day)
        self._league_params: dict[str, dict] = {}  # league_name -> fitted params
        self._fitted = False

    def train(
        self, matches_df: pd.DataFrame, features_df: pd.DataFrame
    ) -> TrainingResult:
        """Train Dixon-Coles per league.

        Args:
            matches_df: Raw match data with home_team, away_team, home_goals, away_goals,
                        date_unix, league_name.
            features_df: Unused (Poisson uses raw match data).
        """
        start = time.monotonic()

        required = {"home_team", "away_team", "home_goals", "away_goals", "date_unix", "league_name"}
        missing = required - set(matches_df.columns)
        if missing:
            raise StrategyTrainingError(self.slug, f"Missing columns: {missing}")

        df = matches_df.dropna(subset=list(required)).copy()
        df = df.sort_values("date_unix")

        leagues = df["league_name"].unique()
        self._league_params = {}

        for league in leagues:
            league_df = df[df["league_name"] == league]
            if len(league_df) < 40:
                continue  # skip leagues with too little data

            try:
                params = self._fit_league(league_df)
                self._league_params[league] = params
            except Exception as exc:
                # Log and skip failed leagues
                print(f"  Warning: Dixon-Coles failed for {league}: {exc}")
                continue

        if not self._league_params:
            raise StrategyTrainingError(self.slug, "No leagues fitted successfully")

        self._fitted = True
        duration = time.monotonic() - start

        return TrainingResult(
            accuracy={"result": None, "over25": None, "btts": None},
            log_loss={"result": None, "over25": None, "btts": None},
            num_samples=len(df),
            duration_seconds=round(duration, 2),
            metadata={
                "leagues_fitted": str(len(self._league_params)),
                "leagues_total": str(len(leagues)),
            },
        )

    def _fit_league(self, league_df: pd.DataFrame) -> dict:
        """Fit Dixon-Coles for a single league."""
        teams = sorted(set(league_df["home_team"].unique()) |
                       set(league_df["away_team"].unique()))
        team_to_idx = {t: i for i, t in enumerate(teams)}
        n = len(teams)

        home_idx = league_df["home_team"].map(team_to_idx).values
        away_idx = league_df["away_team"].map(team_to_idx).values
        home_goals = league_df["home_goals"].values.astype(int)
        away_goals = league_df["away_goals"].values.astype(int)

        # Time decay weights
        max_date = league_df["date_unix"].max()
        days_ago = (max_date - league_df["date_unix"].values) / 86400.0
        weights = np.exp(-self._xi * days_ago)

        # Initial params: attack=0, defense=0, gamma=0.25, rho=-0.05
        # Sum-to-zero trick: only n-1 defense params
        x0 = np.zeros(2 * n - 1 + 2)
        x0[-2] = 0.25  # gamma (home advantage)
        x0[-1] = -0.05  # rho

        # Bounds: rho in [-0.5, 0.5], others unbounded
        bounds = [(None, None)] * (2 * n - 1)
        bounds.append((None, None))  # gamma
        bounds.append((-0.5, 0.5))  # rho

        result = minimize(
            _dc_log_likelihood,
            x0,
            args=(teams, home_goals, away_goals, home_idx, away_idx, weights),
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 1000, "ftol": 1e-8},
        )

        attack = result.x[:n]
        beta_free = result.x[n:2 * n - 1]
        beta_last = -np.sum(beta_free)
        defense = np.concatenate([beta_free, [beta_last]])
        gamma = result.x[-2]
        rho = result.x[-1]

        return {
            "teams": teams,
            "attack": attack.tolist(),
            "defense": defense.tolist(),
            "gamma": float(gamma),
            "rho": float(rho),
            "converged": result.success,
        }

    def predict(
        self, matches_df: pd.DataFrame, features_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Predict probabilities using fitted Dixon-Coles parameters.

        Uses matches_df for team names and league. Returns DataFrame with
        match_id, prob_H, prob_D, prob_A, prob_over25, prob_btts.
        """
        if not self._fitted:
            raise StrategyPredictionError(self.slug, "Model not fitted")

        # Use features_df for match_id, matches_df for league context
        # If features_df has the data we need, use it; otherwise fall back to matches_df
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
                "prob_over25": probs[3],
                "prob_btts": probs[4],
            })

        return pd.DataFrame(results)

    def _predict_match(self, home: str, away: str, league: str | None) -> tuple[float, ...]:
        """Predict a single match. Returns (H, D, A, O2.5, BTTS)."""
        params = self._league_params.get(league) if league else None

        if params is None:
            # Fall back to NaN for unknown leagues
            return (float("nan"),) * 5

        teams = params["teams"]
        if home not in teams or away not in teams:
            return (float("nan"),) * 5

        attack = np.array(params["attack"])
        defense = np.array(params["defense"])
        gamma = params["gamma"]
        rho = params["rho"]

        hi = teams.index(home)
        ai = teams.index(away)

        lam = math.exp(attack[hi] + defense[ai] + gamma)
        mu = math.exp(attack[ai] + defense[hi])

        matrix = _goal_matrix(lam, mu, rho)

        prob_H = float(np.sum(np.tril(matrix, -1)))  # home wins: row > col
        prob_D = float(np.sum(np.diag(matrix)))
        prob_A = float(np.sum(np.triu(matrix, 1)))  # away wins: col > row

        # Over 2.5: 1 - P(total <= 2)
        prob_o25 = 1.0 - float(
            matrix[0, 0] + matrix[0, 1] + matrix[0, 2]
            + matrix[1, 0] + matrix[1, 1]
            + matrix[2, 0]
        )

        # BTTS: P(home >= 1 and away >= 1)
        prob_btts = float(np.sum(matrix[1:, 1:]))

        return (prob_H, prob_D, prob_A, prob_o25, prob_btts)

    def save(self, path: Path) -> None:
        """Save per-league parameters as JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "xi": self._xi,
            "league_params": self._league_params,
        }
        path.write_text(json.dumps(data, indent=2))

    def load(self, path: Path) -> bool:
        """Load parameters from JSON."""
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text())
            self._xi = data["xi"]
            self._league_params = data["league_params"]
            self._fitted = bool(self._league_params)
            return True
        except Exception:
            return False

    @property
    def is_fitted(self) -> bool:
        return self._fitted
