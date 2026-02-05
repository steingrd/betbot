"""
Value Bet Finder

Compares model probabilities to bookmaker odds to find value bets.
"""

import pandas as pd
import numpy as np
from typing import Optional, List
from pathlib import Path


class ValueBetFinder:
    """Find value bets by comparing model probabilities to odds"""

    def __init__(self, min_edge: float = 0.05, min_odds: float = 1.5, max_odds: float = 10.0):
        """
        Args:
            min_edge: Minimum edge (model_prob - implied_prob) to consider a value bet
            min_odds: Minimum odds to consider (avoid very low odds)
            max_odds: Maximum odds to consider (avoid very high variance)
        """
        self.min_edge = min_edge
        self.min_odds = min_odds
        self.max_odds = max_odds

    def odds_to_prob(self, odds: float) -> float:
        """Convert decimal odds to implied probability"""
        if odds <= 0:
            return 0
        return 1 / odds

    def prob_to_odds(self, prob: float) -> float:
        """Convert probability to fair odds"""
        if prob <= 0:
            return 0
        return 1 / prob

    def calculate_edge(self, model_prob: float, odds: float) -> float:
        """Calculate edge: model probability - implied probability"""
        implied_prob = self.odds_to_prob(odds)
        return model_prob - implied_prob

    def kelly_fraction(self, model_prob: float, odds: float, fraction: float = 0.25) -> float:
        """
        Calculate Kelly criterion stake as fraction of bankroll.
        Uses fractional Kelly (default 25%) for reduced variance.

        Returns fraction of bankroll to stake (0 if no edge)
        """
        implied_prob = self.odds_to_prob(odds)
        edge = model_prob - implied_prob

        if edge <= 0:
            return 0

        # Full Kelly: (p * odds - 1) / (odds - 1)
        # where p = model_prob, odds = decimal odds
        full_kelly = (model_prob * odds - 1) / (odds - 1)

        # Apply fractional Kelly
        return max(0, full_kelly * fraction)

    def find_value_bets(self, predictions: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
        """
        Find value bets from predictions.

        Args:
            predictions: DataFrame with model probabilities (prob_H, prob_D, prob_A, etc.)
            features: DataFrame with odds data

        Returns:
            DataFrame of value bets
        """

        # Merge predictions with odds
        merged = predictions.merge(
            features[["match_id", "odds_home", "odds_draw", "odds_away",
                     "odds_over_25", "odds_btts_yes", "target_result",
                     "target_over_25", "target_btts"]],
            on="match_id"
        )

        value_bets = []

        for _, row in merged.iterrows():
            match_info = {
                "match_id": row["match_id"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "game_week": row["game_week"],
            }

            # Check each market
            markets = [
                ("Home", row["prob_H"], row["odds_home"], row["target_result"] == "H"),
                ("Draw", row["prob_D"], row["odds_draw"], row["target_result"] == "D"),
                ("Away", row["prob_A"], row["odds_away"], row["target_result"] == "A"),
                ("Over 2.5", row["prob_over25"], row["odds_over_25"], row["target_over_25"] == 1),
                ("BTTS", row["prob_btts"], row["odds_btts_yes"], row["target_btts"] == 1),
            ]

            for market, model_prob, odds, actual_win in markets:
                if odds is None or odds <= 0:
                    continue

                # Check odds bounds
                if odds < self.min_odds or odds > self.max_odds:
                    continue

                edge = self.calculate_edge(model_prob, odds)

                if edge >= self.min_edge:
                    kelly = self.kelly_fraction(model_prob, odds)

                    value_bets.append({
                        **match_info,
                        "market": market,
                        "model_prob": model_prob,
                        "odds": odds,
                        "implied_prob": self.odds_to_prob(odds),
                        "edge": edge,
                        "kelly_fraction": kelly,
                        "actual_win": actual_win,
                    })

        return pd.DataFrame(value_bets)

    def backtest(self, value_bets: pd.DataFrame, stake: float = 10.0) -> dict:
        """
        Backtest value bets with flat stake.

        Args:
            value_bets: DataFrame from find_value_bets()
            stake: Fixed stake per bet

        Returns:
            Backtest results
        """

        if len(value_bets) == 0:
            return {"error": "No value bets to backtest"}

        total_staked = len(value_bets) * stake
        total_returned = 0
        wins = 0

        for _, bet in value_bets.iterrows():
            if bet["actual_win"]:
                total_returned += stake * bet["odds"]
                wins += 1

        profit = total_returned - total_staked
        roi = (profit / total_staked) * 100 if total_staked > 0 else 0

        return {
            "total_bets": len(value_bets),
            "wins": wins,
            "win_rate": wins / len(value_bets),
            "total_staked": total_staked,
            "total_returned": total_returned,
            "profit": profit,
            "roi": roi,
            "avg_odds": value_bets["odds"].mean(),
            "avg_edge": value_bets["edge"].mean(),
        }

    def backtest_by_market(self, value_bets: pd.DataFrame, stake: float = 10.0) -> pd.DataFrame:
        """Backtest split by market"""

        results = []
        for market in value_bets["market"].unique():
            market_bets = value_bets[value_bets["market"] == market]
            result = self.backtest(market_bets, stake)
            result["market"] = market
            results.append(result)

        return pd.DataFrame(results)


def run_backtest():
    """Run full backtest on historical data"""

    from src.data.data_processor import DataProcessor
    from src.features.feature_engineering import FeatureEngineer
    from src.models.match_predictor import MatchPredictor

    print("=" * 60)
    print("VALUE BET BACKTEST")
    print("=" * 60)

    # Load data
    processor = DataProcessor()
    matches = processor.load_matches()
    print(f"Loaded {len(matches)} matches")

    # Generate features
    engineer = FeatureEngineer(matches)
    features = engineer.generate_features()
    print(f"Generated features for {len(features)} matches")

    # Load trained model
    predictor = MatchPredictor()
    predictor.load()
    print("Loaded trained model")

    # Make predictions
    predictions = predictor.predict(features)
    print(f"Made predictions for {len(predictions)} matches")

    # Find value bets
    finder = ValueBetFinder(min_edge=0.05, min_odds=1.5, max_odds=8.0)
    value_bets = finder.find_value_bets(predictions, features)
    print(f"\nFound {len(value_bets)} value bets")

    if len(value_bets) == 0:
        print("No value bets found. Try lowering min_edge.")
        return

    # Overall backtest
    print("\n" + "=" * 60)
    print("OVERALL RESULTS")
    print("=" * 60)
    results = finder.backtest(value_bets, stake=10.0)
    for key, value in results.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")

    # By market
    print("\n" + "=" * 60)
    print("RESULTS BY MARKET")
    print("=" * 60)
    by_market = finder.backtest_by_market(value_bets, stake=10.0)
    print(by_market[["market", "total_bets", "win_rate", "profit", "roi"]].to_string(index=False))

    # Show best value bets
    print("\n" + "=" * 60)
    print("TOP 10 VALUE BETS (by edge)")
    print("=" * 60)
    top_bets = value_bets.nlargest(10, "edge")
    for _, bet in top_bets.iterrows():
        result = "✓" if bet["actual_win"] else "✗"
        print(f"{result} {bet['home_team']} vs {bet['away_team']}: {bet['market']}")
        print(f"   Model: {bet['model_prob']:.1%} | Odds: {bet['odds']:.2f} | Edge: {bet['edge']:.1%}")

    return value_bets, results


if __name__ == "__main__":
    run_backtest()
