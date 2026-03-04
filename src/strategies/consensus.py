"""
Consensus Engine.

Finds value bets where multiple strategies independently agree there is value.
"""

import math

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field


class StrategySignal(BaseModel):
    """A single strategy's prediction for a market."""

    strategy_slug: str
    strategy_name: str
    model_prob: float = Field(ge=0.0, le=1.0)
    edge: float
    is_value: bool


class ConsensusBet(BaseModel):
    """Aggregated consensus for a match-market pair."""

    match_id: str
    home_team: str
    away_team: str
    league: str = ""
    kickoff: str = ""
    market: str
    odds: float = Field(gt=0.0)
    implied_prob: float = Field(ge=0.0, le=1.0)
    consensus_count: int
    total_strategies: int
    signals: list[StrategySignal]

    @property
    def agreement_ratio(self) -> float:
        if not self.signals:
            return 0.0
        return sum(1 for s in self.signals if s.is_value) / len(self.signals)


# Map market names to the probability column in strategy output
MARKET_PROB_COL = {
    "Home": "prob_H",
    "Draw": "prob_D",
    "Away": "prob_A",
    "Over 2.5": "prob_over25",
    "BTTS": "prob_btts",
}

# Map market names to odds columns in the features/odds DataFrame
MARKET_ODDS_COL = {
    "Home": "odds_home",
    "Draw": "odds_draw",
    "Away": "odds_away",
    "Over 2.5": "odds_over_25",
    "BTTS": "odds_btts_yes",
}


class ConsensusEngine:
    """Finds value bets where multiple strategies agree."""

    def find_consensus_bets(
        self,
        strategy_predictions: dict[str, pd.DataFrame],
        strategy_names: dict[str, str],
        odds_df: pd.DataFrame,
        min_edge: float = 0.05,
    ) -> list[ConsensusBet]:
        """Find consensus bets across all strategies.

        Args:
            strategy_predictions: {slug: predictions_df} with prob_H, prob_D, etc.
            strategy_names: {slug: human_readable_name}
            odds_df: DataFrame with match_id, home_team, away_team, league_name,
                     odds_home, odds_draw, odds_away, odds_over_25, odds_btts_yes.
            min_edge: Minimum edge for a strategy to flag value.

        Returns:
            List of ConsensusBet for every match-market pair that has at least
            one strategy flagging value. Client filters by consensus_count >= threshold.
        """
        consensus_bets = []

        # Normalize 1X2 implied probabilities per match
        odds_normalized = self._normalize_1x2(odds_df)

        for _, odds_row in odds_normalized.iterrows():
            match_id = str(odds_row.get("match_id", odds_row.get("id", "")))
            home_team = str(odds_row.get("home_team", ""))
            away_team = str(odds_row.get("away_team", ""))
            league = str(odds_row.get("league_name", ""))
            kickoff = str(odds_row.get("kickoff", ""))

            for market, prob_col in MARKET_PROB_COL.items():
                odds_col = MARKET_ODDS_COL[market]
                odds_val = odds_row.get(odds_col)

                if odds_val is None or (isinstance(odds_val, float) and math.isnan(odds_val)):
                    continue
                if odds_val <= 0:
                    continue

                # Use normalized implied prob for 1X2, raw for binary markets
                if market in ("Home", "Draw", "Away"):
                    implied_prob = odds_row.get(f"implied_{market.lower()}", 1.0 / odds_val)
                else:
                    implied_prob = 1.0 / odds_val

                signals = []
                for slug, preds_df in strategy_predictions.items():
                    # Find this match in the strategy's predictions
                    match_row = preds_df[preds_df["match_id"] == odds_row.get("match_id", odds_row.get("id"))]
                    if match_row.empty:
                        continue

                    model_prob = float(match_row[prob_col].iloc[0])
                    if math.isnan(model_prob):
                        continue  # Strategy doesn't support this market

                    edge = model_prob - implied_prob
                    signals.append(StrategySignal(
                        strategy_slug=slug,
                        strategy_name=strategy_names.get(slug, slug),
                        model_prob=model_prob,
                        edge=round(edge, 4),
                        is_value=edge >= min_edge,
                    ))

                if not signals:
                    continue

                consensus_count = sum(1 for s in signals if s.is_value)

                # Only include if at least one strategy flags value
                if consensus_count == 0:
                    continue

                consensus_bets.append(ConsensusBet(
                    match_id=match_id,
                    home_team=home_team,
                    away_team=away_team,
                    league=league,
                    kickoff=kickoff,
                    market=market,
                    odds=float(odds_val),
                    implied_prob=round(float(implied_prob), 4),
                    consensus_count=consensus_count,
                    total_strategies=len(signals),
                    signals=signals,
                ))

        return consensus_bets

    def _normalize_1x2(self, odds_df: pd.DataFrame) -> pd.DataFrame:
        """Add normalized 1X2 implied probabilities to odds DataFrame."""
        df = odds_df.copy()

        if "odds_home" in df.columns and "odds_draw" in df.columns and "odds_away" in df.columns:
            raw_h = 1.0 / df["odds_home"].replace(0, np.nan)
            raw_d = 1.0 / df["odds_draw"].replace(0, np.nan)
            raw_a = 1.0 / df["odds_away"].replace(0, np.nan)
            total = raw_h + raw_d + raw_a

            df["implied_home"] = raw_h / total
            df["implied_draw"] = raw_d / total
            df["implied_away"] = raw_a / total

        return df
