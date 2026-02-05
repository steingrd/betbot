#!/usr/bin/env python3
"""
Run out-of-sample backtest on historical data.

This script trains on earlier seasons and tests on a hold-out season
to provide realistic performance estimates.
"""

import sys
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.data_processor import DataProcessor
from features.feature_engineering import FeatureEngineer
from models.match_predictor import MatchPredictor
from analysis.value_finder import ValueBetFinder


def get_season_year(date, season_start_month: int = 8):
    """
    Determine season year from date.

    Args:
        date: datetime object
        season_start_month: Month when season starts (default 8 = August)
            - Use 8 for European leagues (Aug-May)
            - Use 1 for calendar-year leagues (MLS, etc.)

    Returns:
        Season year (year when season started)
    """
    if date.month >= season_start_month:
        return date.year
    return date.year - 1


# Season start month (8 = August for European leagues)
# Change to 1 for calendar-year leagues like MLS
SEASON_START_MONTH = 8


def get_season_info(features: pd.DataFrame) -> pd.DataFrame:
    """Get info about available seasons"""
    if "date_unix" not in features.columns:
        return pd.DataFrame()

    features = features.copy()
    features["date"] = pd.to_datetime(features["date_unix"], unit="s")
    features["year"] = features["date"].dt.year
    features["month"] = features["date"].dt.month

    # Determine season based on configured start month
    features["season_year"] = features["date"].apply(
        lambda d: get_season_year(d, SEASON_START_MONTH)
    )

    season_stats = features.groupby("season_year").agg(
        matches=("match_id", "count"),
        start=("date", "min"),
        end=("date", "max")
    ).reset_index()

    return season_stats


def run_out_of_sample_backtest(holdout_seasons: int = 1):
    """
    Run proper out-of-sample backtest.

    Args:
        holdout_seasons: Number of most recent seasons to use as test set
    """
    print("=" * 60)
    print("OUT-OF-SAMPLE VALUE BET BACKTEST")
    print("=" * 60)

    # Load data
    processor = DataProcessor()
    matches = processor.load_matches()
    print(f"Loaded {len(matches)} matches")

    # Generate features
    engineer = FeatureEngineer(matches)
    features = engineer.generate_features()
    print(f"Generated features for {len(features)} matches")

    # Get season info
    season_info = get_season_info(features)
    print(f"\nAvailable seasons:")
    for _, row in season_info.iterrows():
        print(f"  {int(row['season_year'])}/{int(row['season_year'])+1}: "
              f"{row['matches']} matches ({row['start'].strftime('%Y-%m-%d')} - {row['end'].strftime('%Y-%m-%d')})")

    # Determine train/test split by season
    features["date"] = pd.to_datetime(features["date_unix"], unit="s")
    features["season_year"] = features["date"].apply(
        lambda d: get_season_year(d, SEASON_START_MONTH)
    )

    all_seasons = sorted(features["season_year"].unique())

    if len(all_seasons) < 2:
        print("\nError: Need at least 2 seasons for out-of-sample backtest")
        return

    train_seasons = all_seasons[:-holdout_seasons]
    test_seasons = all_seasons[-holdout_seasons:]

    print(f"\nTrain seasons: {[f'{s}/{s+1}' for s in train_seasons]}")
    print(f"Test seasons (hold-out): {[f'{s}/{s+1}' for s in test_seasons]}")

    train_features = features[features["season_year"].isin(train_seasons)].copy()
    test_features = features[features["season_year"].isin(test_seasons)].copy()

    print(f"\nTrain set: {len(train_features)} matches")
    print(f"Test set: {len(test_features)} matches")

    # Train model on training data only
    print("\n" + "=" * 60)
    print("TRAINING MODEL (on historical seasons only)")
    print("=" * 60)

    predictor = MatchPredictor()
    # Use all training data since we have external hold-out season(s)
    results = predictor.train(train_features, test_size=0.0)

    # Make predictions on hold-out test set
    print("\n" + "=" * 60)
    print("EVALUATING ON HOLD-OUT SEASON(S)")
    print("=" * 60)

    predictions = predictor.predict(test_features)
    print(f"Made predictions for {len(predictions)} matches")

    # Find value bets with different thresholds
    for min_edge in [0.03, 0.05, 0.08, 0.10]:
        print(f"\n{'=' * 60}")
        print(f"MIN EDGE: {min_edge:.0%}")
        print("=" * 60)

        finder = ValueBetFinder(min_edge=min_edge, min_odds=1.5, max_odds=8.0)
        value_bets = finder.find_value_bets(predictions, test_features)
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
    print("SAMPLE VALUE BETS FROM HOLD-OUT SEASON (edge >= 8%)")
    print("=" * 60)

    finder = ValueBetFinder(min_edge=0.08, min_odds=1.5, max_odds=8.0)
    value_bets = finder.find_value_bets(predictions, test_features)

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


def run_in_sample_backtest():
    """Run in-sample backtest for comparison (NOT recommended for evaluation)"""
    print("=" * 60)
    print("IN-SAMPLE BACKTEST (for reference only - overly optimistic)")
    print("=" * 60)
    print("WARNING: This uses same data for training and testing.")
    print("Results will be overly optimistic. Use out-of-sample instead.\n")

    # Load data
    processor = DataProcessor()
    matches = processor.load_matches()

    # Generate features
    engineer = FeatureEngineer(matches)
    features = engineer.generate_features()

    # Load trained model
    predictor = MatchPredictor()
    predictor.load()

    # Make predictions
    predictions = predictor.predict(features)

    # Find and evaluate value bets
    finder = ValueBetFinder(min_edge=0.05, min_odds=1.5, max_odds=8.0)
    value_bets = finder.find_value_bets(predictions, features)

    results = finder.backtest(value_bets, stake=10.0)
    print(f"Found {len(value_bets)} value bets")
    print(f"ROI: {results['roi']:.1f}% (IN-SAMPLE - not reliable)")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run backtest on historical data")
    parser.add_argument("--in-sample", action="store_true",
                        help="Run in-sample backtest (not recommended)")
    parser.add_argument("--holdout-seasons", type=int, default=1,
                        help="Number of seasons to hold out for testing (default: 1)")
    args = parser.parse_args()

    if args.in_sample:
        run_in_sample_backtest()
    else:
        run_out_of_sample_backtest(holdout_seasons=args.holdout_seasons)


if __name__ == "__main__":
    main()
