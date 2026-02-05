#!/usr/bin/env python3
"""
Run out-of-sample backtest on historical data.

Uses season_id and per-league holdout for proper train/test splits.
Works correctly for both calendar-year leagues (Norway) and Aug-May leagues (PL).
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.data_processor import DataProcessor
from features.feature_engineering import FeatureEngineer
from models.match_predictor import MatchPredictor
from analysis.value_finder import ValueBetFinder


def format_season_label(start_date: int, end_date: int) -> str:
    """
    Create human-readable season label from date range.

    - Calendar year (Jan-Dec): "2024"
    - Aug-May season: "2024/2025"
    """
    if start_date is None or end_date is None:
        return "Unknown"

    start = datetime.fromtimestamp(start_date)
    end = datetime.fromtimestamp(end_date)

    # If season spans two calendar years and starts in Aug-Dec, it's a Aug-May style
    if start.year != end.year and start.month >= 7:
        return f"{start.year}/{end.year}"
    else:
        # Calendar year season
        return str(start.year)


def get_season_info_by_league(processor: DataProcessor) -> pd.DataFrame:
    """
    Get season info grouped by league with actual date ranges.

    Uses season_id and start/end dates from database, not month heuristics.
    """
    seasons = processor.get_seasons_by_league()

    if len(seasons) == 0:
        print("WARNING: No season metadata found. Run download_all_leagues.py first.")
        return pd.DataFrame()

    # Add display label
    seasons["display_label"] = seasons.apply(
        lambda r: format_season_label(r["start_date"], r["end_date"]), axis=1
    )

    return seasons


def split_train_test_per_league(
    features: pd.DataFrame,
    seasons: pd.DataFrame,
    holdout_seasons: int = 1
) -> tuple:
    """
    Split data into train/test per league.

    For each league, holds out the N most recent seasons (by start_date).
    This handles both calendar-year and Aug-May seasons correctly.

    Args:
        features: DataFrame with match features (must have season_id)
        seasons: DataFrame with season metadata (from get_seasons_by_league)
        holdout_seasons: Number of most recent seasons per league to hold out

    Returns:
        (train_features, test_features, split_info)
    """
    if "season_id" not in features.columns:
        raise ValueError("features must have season_id column")

    # Get league_id for each season
    season_to_league = seasons.set_index("season_id")["league_id"].to_dict()
    features = features.copy()

    # Add league_id to features if missing
    if "league_id" not in features.columns or features["league_id"].isna().all():
        features["league_id"] = features["season_id"].map(season_to_league)

    train_seasons = []
    test_seasons = []
    split_info = []

    # Process each league separately
    for league_id in features["league_id"].dropna().unique():
        league_seasons = seasons[seasons["league_id"] == league_id].copy()

        if len(league_seasons) < 2:
            league_name = league_seasons["league_name"].iloc[0] if len(league_seasons) > 0 else f"League {league_id}"
            print(f"  WARNING: {league_name} has only {len(league_seasons)} season(s), skipping holdout")
            # Include all in training
            train_seasons.extend(league_seasons["season_id"].tolist())
            split_info.append({
                "league_id": league_id,
                "league_name": league_name,
                "train_seasons": len(league_seasons),
                "test_seasons": 0,
                "warning": "< 2 seasons"
            })
            continue

        # Sort by start_date to get chronological order
        league_seasons = league_seasons.sort_values("start_date")

        # Split: all but last N for training, last N for testing
        train_season_ids = league_seasons["season_id"].iloc[:-holdout_seasons].tolist()
        test_season_ids = league_seasons["season_id"].iloc[-holdout_seasons:].tolist()

        train_seasons.extend(train_season_ids)
        test_seasons.extend(test_season_ids)

        league_name = league_seasons["league_name"].iloc[0]
        train_labels = league_seasons[league_seasons["season_id"].isin(train_season_ids)]["display_label"].tolist()
        test_labels = league_seasons[league_seasons["season_id"].isin(test_season_ids)]["display_label"].tolist()

        split_info.append({
            "league_id": league_id,
            "league_name": league_name,
            "country": league_seasons["country"].iloc[0],
            "train_seasons": len(train_season_ids),
            "test_seasons": len(test_season_ids),
            "train_labels": train_labels,
            "test_labels": test_labels
        })

    train_features = features[features["season_id"].isin(train_seasons)].copy()
    test_features = features[features["season_id"].isin(test_seasons)].copy()

    return train_features, test_features, split_info


def verify_no_leakage(train_features: pd.DataFrame, test_features: pd.DataFrame) -> bool:
    """Verify that max(train_date) < min(test_date) per league"""
    all_ok = True

    for league_id in test_features["league_id"].dropna().unique():
        train_league = train_features[train_features["league_id"] == league_id]
        test_league = test_features[test_features["league_id"] == league_id]

        if len(train_league) == 0 or len(test_league) == 0:
            continue

        max_train = train_league["date_unix"].max()
        min_test = test_league["date_unix"].min()

        if max_train >= min_test:
            print(f"  WARNING: Potential leakage in league {league_id}!")
            print(f"    Max train date: {datetime.fromtimestamp(max_train)}")
            print(f"    Min test date: {datetime.fromtimestamp(min_test)}")
            all_ok = False

    return all_ok


def run_out_of_sample_backtest(holdout_seasons: int = 1):
    """
    Run proper out-of-sample backtest with per-league holdout.

    Args:
        holdout_seasons: Number of most recent seasons per league to use as test set
    """
    print("=" * 60)
    print("OUT-OF-SAMPLE VALUE BET BACKTEST (per-league holdout)")
    print("=" * 60)

    # Load data
    processor = DataProcessor()
    matches = processor.load_matches()
    print(f"Loaded {len(matches)} matches")

    # Load season metadata
    seasons = get_season_info_by_league(processor)
    if len(seasons) == 0:
        print("\nERROR: No season metadata. Run 'python scripts/download_all_leagues.py' first.")
        print("This will populate the seasons table with league info needed for proper splits.")
        return

    print(f"Loaded {len(seasons)} seasons across {seasons['league_id'].nunique()} leagues")

    # Show available leagues and seasons
    print(f"\nAvailable leagues and seasons:")
    for league_id in seasons["league_id"].unique():
        league_seasons = seasons[seasons["league_id"] == league_id].sort_values("start_date")
        league_name = f"{league_seasons['country'].iloc[0]} {league_seasons['league_name'].iloc[0]}"
        season_labels = league_seasons["display_label"].tolist()
        match_count = league_seasons["match_count"].sum()
        print(f"  {league_name}: {len(league_seasons)} seasons ({', '.join(season_labels)}) - {match_count} matches")

    # Load or generate features (with caching)
    features_cache = Path(__file__).parent.parent / "data" / "processed" / "features.csv"

    if features_cache.exists():
        print(f"\nLoading cached features from {features_cache.name}...")
        features = pd.read_csv(features_cache)
        print(f"Loaded {len(features)} cached features")

        # Check if cache has required columns
        if "season_id" not in features.columns or "league_id" not in features.columns:
            print("Cache missing season_id/league_id - regenerating...")
            engineer = FeatureEngineer(matches)
            features = engineer.generate_features()
            features.to_csv(features_cache, index=False)
            print(f"Generated and cached {len(features)} features")
    else:
        print(f"\nGenerating features (this takes a while first time)...")
        engineer = FeatureEngineer(matches)
        features = engineer.generate_features()
        features.to_csv(features_cache, index=False)
        print(f"Generated and cached {len(features)} features to {features_cache.name}")

    # Split train/test per league
    print(f"\nSplitting data (holding out {holdout_seasons} season(s) per league)...")
    train_features, test_features, split_info = split_train_test_per_league(
        features, seasons, holdout_seasons
    )

    # Show split info
    print(f"\nTrain/test split per league:")
    for info in split_info:
        if "warning" in info:
            print(f"  {info['league_name']}: {info['train_seasons']} train, {info['test_seasons']} test [{info['warning']}]")
        else:
            print(f"  {info['country']} {info['league_name']}:")
            print(f"    Train: {info['train_labels']}")
            print(f"    Test:  {info['test_labels']}")

    print(f"\nTrain set: {len(train_features)} matches")
    print(f"Test set: {len(test_features)} matches")

    if len(test_features) == 0:
        print("\nERROR: No test data! Need at least 2 seasons per league for holdout.")
        return

    # Verify no data leakage
    print(f"\nVerifying no data leakage...")
    if verify_no_leakage(train_features, test_features):
        print("  ✓ No leakage detected (max train date < min test date per league)")
    else:
        print("  ✗ Potential leakage detected! Check warnings above.")

    # Train model on training data only
    print("\n" + "=" * 60)
    print("TRAINING MODEL (on historical seasons only)")
    print("=" * 60)

    predictor = MatchPredictor()
    # Use all training data since we have external hold-out
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
        bt_results = finder.backtest(value_bets, stake=10.0)
        print(f"\n  Total bets: {bt_results['total_bets']}")
        print(f"  Win rate: {bt_results['win_rate']:.1%}")
        print(f"  Avg odds: {bt_results['avg_odds']:.2f}")
        print(f"  Total staked: kr {bt_results['total_staked']:.0f}")
        print(f"  Profit: kr {bt_results['profit']:.2f}")
        print(f"  ROI: {bt_results['roi']:.1f}%")

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
                        help="Number of seasons per league to hold out for testing (default: 1)")
    parser.add_argument("--regenerate", action="store_true",
                        help="Force regeneration of features (ignore cache)")
    args = parser.parse_args()

    if args.regenerate:
        cache_path = Path(__file__).parent.parent / "data" / "processed" / "features.csv"
        if cache_path.exists():
            cache_path.unlink()
            print(f"Deleted feature cache: {cache_path}")

    if args.in_sample:
        run_in_sample_backtest()
    else:
        run_out_of_sample_backtest(holdout_seasons=args.holdout_seasons)


if __name__ == "__main__":
    main()
