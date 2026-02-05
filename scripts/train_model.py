#!/usr/bin/env python3
"""
BetBot Model Training Script

Generates features and trains models with:
- Deterministic seeds for reproducibility
- Model versioning with timestamps
- Metrics logging for traceability
- Evaluation report saved per run
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.data_processor import DataProcessor
from features.feature_engineering import FeatureEngineer
from models.match_predictor import MatchPredictor

# Reproducibility seeds (documented here for reference)
RANDOM_SEEDS = {
    "xgboost": 42,
    "train_test_split": 42,  # Now using time-based split, but kept for reference
    "calibration_cv": 3,     # CV folds for calibration
}


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


def save_training_report(report: dict, reports_dir: Path):
    """Save training report to JSON file with timestamp"""
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = report["timestamp"]
    filename = f"training_report_{timestamp.replace(':', '-').replace(' ', '_')}.json"
    filepath = reports_dir / filename

    with open(filepath, "w") as f:
        json.dump(report, f, indent=2, default=str)

    # Also save as latest
    latest_path = reports_dir / "latest_training_report.json"
    with open(latest_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    return filepath


def main():
    start_time = time.time()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print("=" * 60)
    print("BETBOT - MODEL TRAINING")
    print("=" * 60)
    print(f"Started: {timestamp}")
    print()
    print("Reproducibility settings:")
    for key, value in RANDOM_SEEDS.items():
        print(f"  {key}: {value}")
    print()

    # Initialize report
    report = {
        "timestamp": timestamp,
        "random_seeds": RANDOM_SEEDS,
        "steps": {},
        "model_performance": {},
        "data_stats": {},
    }

    # Step 1: Load matches
    step_start = time.time()
    print("[1/4] Loading matches from database...")

    processor = DataProcessor()
    matches = processor.load_matches()

    elapsed = time.time() - step_start
    print(f"       Loaded {len(matches):,} matches ({format_duration(elapsed)})")
    print()

    report["steps"]["load_matches"] = {
        "duration_seconds": elapsed,
        "matches_loaded": len(matches)
    }
    report["data_stats"]["total_matches"] = len(matches)

    # Step 2: Generate features
    step_start = time.time()
    print("[2/4] Generating features...")
    print("       Calculating form, H2H, positions for each match")
    print("       Using time-based split (train on earlier, test on later)")
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

    report["steps"]["generate_features"] = {
        "duration_seconds": elapsed,
        "features_generated": len(features_df),
        "feature_columns": len(features_df.columns)
    }
    report["data_stats"]["features_generated"] = len(features_df)

    # Step 3: Train models
    step_start = time.time()
    print("[3/4] Training ML models (1X2, Over 2.5, BTTS)...")
    print("       Using time-based train/test split (no data leakage)")
    print()

    predictor = MatchPredictor()
    results = predictor.train(features_df)

    elapsed = time.time() - step_start
    print()
    print(f"       All models trained ({format_duration(elapsed)})")
    print()

    report["steps"]["train_models"] = {
        "duration_seconds": elapsed,
    }
    report["model_performance"] = {
        "result_1x2": {
            "accuracy": results["result"]["accuracy"],
            "log_loss": results["result"]["log_loss"],
            "classes": results["result"]["classes"]
        },
        "over_25": {
            "accuracy": results["over25"]["accuracy"],
            "log_loss": results["over25"]["log_loss"]
        },
        "btts": {
            "accuracy": results["btts"]["accuracy"],
            "log_loss": results["btts"]["log_loss"]
        }
    }

    # Step 4: Save models with versioning
    step_start = time.time()
    print("[4/4] Saving models...")

    # Save with timestamp for versioning
    model_version = datetime.now().strftime('%Y%m%d_%H%M%S')
    versioned_name = f"match_predictor_{model_version}"

    predictor.save()  # Save as default
    predictor.save(versioned_name)  # Save versioned copy

    elapsed = time.time() - step_start
    print(f"       Models saved ({format_duration(elapsed)})")
    print(f"       Default: {predictor.model_dir}/match_predictor.pkl")
    print(f"       Versioned: {predictor.model_dir}/{versioned_name}.pkl")
    print()

    report["steps"]["save_models"] = {
        "duration_seconds": elapsed,
        "model_version": model_version,
        "model_path": str(predictor.model_dir / "match_predictor.pkl"),
        "versioned_path": str(predictor.model_dir / f"{versioned_name}.pkl")
    }

    # Total time
    total_elapsed = time.time() - start_time
    report["total_duration_seconds"] = total_elapsed

    # Save training report
    reports_dir = Path(__file__).parent.parent / "reports"
    report_path = save_training_report(report, reports_dir)

    # Summary
    print("=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"  Total time: {format_duration(total_elapsed)}")
    print(f"  Matches processed: {len(matches):,}")
    print(f"  Features generated: {len(features_df):,}")
    print()
    print("  Model performance (time-based out-of-sample):")
    print(f"    1X2 Result:  {results['result']['accuracy']:.1%} accuracy, {results['result']['log_loss']:.3f} log loss")
    print(f"    Over 2.5:    {results['over25']['accuracy']:.1%} accuracy, {results['over25']['log_loss']:.3f} log loss")
    print(f"    BTTS:        {results['btts']['accuracy']:.1%} accuracy, {results['btts']['log_loss']:.3f} log loss")
    print()
    print(f"  Model version: {model_version}")
    print(f"  Model location: {predictor.model_dir}")
    print(f"  Training report: {report_path}")
    print()
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
