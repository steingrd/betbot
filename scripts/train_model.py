#!/usr/bin/env python3
"""
BetBot Model Training Script

Generates features and trains models with progress output.
"""

import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.data_processor import DataProcessor
from features.feature_engineering import FeatureEngineer
from models.match_predictor import MatchPredictor


def format_duration(seconds):
    """Format seconds as HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


class ProgressTracker:
    def __init__(self):
        self.start_time = time.time()
        self.last_percent = -1

    def update(self, current, total):
        percent = int((current / total) * 100)
        if percent > self.last_percent and percent % 5 == 0:
            elapsed = time.time() - self.start_time
            rate = current / elapsed if elapsed > 0 else 0
            remaining = (total - current) / rate if rate > 0 else 0
            print(f"       {percent:3d}% ({current:,}/{total:,}) - {format_duration(elapsed)} elapsed, ~{format_duration(remaining)} remaining")
            self.last_percent = percent


def main():
    start_time = time.time()

    print("=" * 60)
    print("BETBOT - MODEL TRAINING")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Step 1: Load matches
    step_start = time.time()
    print("[1/4] Loading matches from database...")

    processor = DataProcessor()
    matches = processor.load_matches()

    elapsed = time.time() - step_start
    print(f"       Loaded {len(matches):,} matches ({format_duration(elapsed)})")
    print()

    # Step 2: Generate features
    step_start = time.time()
    print("[2/4] Generating features...")
    print("       Calculating form, H2H, positions for each match")
    print()

    engineer = FeatureEngineer(matches)
    progress = ProgressTracker()

    features_df = engineer.generate_features(min_matches=3, progress_callback=progress.update)

    elapsed = time.time() - step_start
    print()
    print(f"       Generated {len(features_df):,} feature rows ({format_duration(elapsed)})")

    # Save features
    output_path = processor.db_path.parent / "features.csv"
    features_df.to_csv(output_path, index=False)
    print(f"       Saved to {output_path}")
    print()

    # Step 3: Train models
    step_start = time.time()
    print("[3/4] Training ML models (1X2, Over 2.5, BTTS)...")
    print()

    predictor = MatchPredictor()
    results = predictor.train(features_df)

    elapsed = time.time() - step_start
    print()
    print(f"       All models trained ({format_duration(elapsed)})")
    print()

    # Step 4: Save models
    step_start = time.time()
    print("[4/4] Saving models...")

    predictor.save()

    elapsed = time.time() - step_start
    print(f"       Models saved ({format_duration(elapsed)})")
    print()

    # Summary
    total_elapsed = time.time() - start_time
    print("=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"  Total time: {format_duration(total_elapsed)}")
    print(f"  Matches processed: {len(matches):,}")
    print(f"  Features generated: {len(features_df):,}")
    print()
    print("  Model performance:")
    print(f"    1X2 Result:  {results['result']['accuracy']:.1%} accuracy")
    print(f"    Over 2.5:    {results['over25']['accuracy']:.1%} accuracy")
    print(f"    BTTS:        {results['btts']['accuracy']:.1%} accuracy")
    print()
    print(f"  Model location: {predictor.model_dir}")
    print()
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
