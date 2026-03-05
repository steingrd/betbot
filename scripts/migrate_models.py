#!/usr/bin/env python3
"""Migrate existing model files to models/standard/ directory.

Moves models/*.pkl|json -> models/standard/ and creates config.json.
Idempotent — safe to run multiple times.
"""

import shutil
from pathlib import Path

from src.models.model_config import ModelConfig


def migrate():
    models_dir = Path(__file__).parent.parent / "models"
    standard_dir = models_dir / "standard"

    # Check if already migrated
    if (standard_dir / "config.json").exists():
        print("Already migrated — models/standard/config.json exists")
        return

    standard_dir.mkdir(parents=True, exist_ok=True)

    # Move model files
    extensions = ("*.pkl", "*.json")
    moved = []
    for ext in extensions:
        for f in models_dir.glob(ext):
            dest = standard_dir / f.name
            shutil.move(str(f), str(dest))
            moved.append(f.name)
            print(f"  Moved {f.name}")

    # Create config
    config = ModelConfig(
        slug="standard",
        name="Standard",
        strategies=["xgboost", "poisson", "elo", "logreg"],
        is_default=True,
    )
    config.save(models_dir)
    print(f"  Created config.json")

    print(f"\nMigration complete: {len(moved)} files moved to models/standard/")


if __name__ == "__main__":
    migrate()
