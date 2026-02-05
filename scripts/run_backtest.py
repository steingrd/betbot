#!/usr/bin/env python3
"""
Run backtest on historical data
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.data_processor import DataProcessor
from features.feature_engineering import FeatureEngineer
from models.match_predictor import MatchPredictor
from analysis.value_finder import ValueBetFinder


def main():
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

    # Find value bets with different thresholds
    for min_edge in [0.03, 0.05, 0.08, 0.10]:
        print(f"\n{'=' * 60}")
        print(f"MIN EDGE: {min_edge:.0%}")
        print("=" * 60)

        finder = ValueBetFinder(min_edge=min_edge, min_odds=1.5, max_odds=8.0)
        value_bets = finder.find_value_bets(predictions, features)
        print(f"Found {len(value_bets)} value bets")

        if len(value_bets) == 0:
            continue

        # Overall backtest
        results = finder.backtest(value_bets, stake=10.0)
        print(f"\n  Total bets: {results['total_bets']}")
        print(f"  Win rate: {results['win_rate']:.1%}")
        print(f"  Avg odds: {results['avg_odds']:.2f}")
        print(f"  Total staked: kr {results['total_staked']:.0f}")
        print(f"  Profit: kr {results['profit']:.2f}")
        print(f"  ROI: {results['roi']:.1f}%")

        # By market
        print("\n  By market:")
        by_market = finder.backtest_by_market(value_bets, stake=10.0)
        for _, row in by_market.iterrows():
            print(f"    {row['market']:10s}: {row['total_bets']:3.0f} bets, "
                  f"win {row['win_rate']:.0%}, ROI {row['roi']:+.1f}%")

    # Show some examples of value bets
    print("\n" + "=" * 60)
    print("SAMPLE VALUE BETS (edge >= 8%)")
    print("=" * 60)

    finder = ValueBetFinder(min_edge=0.08, min_odds=1.5, max_odds=8.0)
    value_bets = finder.find_value_bets(predictions, features)

    if len(value_bets) > 0:
        top_bets = value_bets.nlargest(15, "edge")
        for _, bet in top_bets.iterrows():
            result = "✓ WON" if bet["actual_win"] else "✗ LOST"
            print(f"\n{bet['home_team']} vs {bet['away_team']}")
            print(f"  Market: {bet['market']}")
            print(f"  Model prob: {bet['model_prob']:.1%}")
            print(f"  Odds: {bet['odds']:.2f} (implied: {bet['implied_prob']:.1%})")
            print(f"  Edge: {bet['edge']:.1%}")
            print(f"  Result: {result}")


if __name__ == "__main__":
    main()
