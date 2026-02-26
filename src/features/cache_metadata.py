"""
Feature cache metadata utilities.

Keeps feature caches safe by binding them to:
- Feature-engine version
- Source match data fingerprint
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


CACHE_METADATA_SCHEMA_VERSION = 1

# Include fields that materially affect generated features.
FINGERPRINT_COLUMNS = [
    "id",
    "season_id",
    "league_id",
    "date_unix",
    "home_team_id",
    "away_team_id",
    "home_goals",
    "away_goals",
    "result",
    "odds_home",
    "odds_draw",
    "odds_away",
    "odds_over_25",
    "odds_btts_yes",
    "btts",
    "over_25",
    "home_ppg",
    "away_ppg",
    "home_overall_ppg",
    "away_overall_ppg",
    "home_xg_prematch",
    "away_xg_prematch",
    "total_xg_prematch",
    "home_attacks",
    "away_attacks",
    "home_dangerous_attacks",
    "away_dangerous_attacks",
    "fs_btts_potential",
    "fs_o25_potential",
    "fs_o35_potential",
]


def compute_source_fingerprint(matches_df: pd.DataFrame) -> str:
    """
    Compute a stable fingerprint of the source match data.

    If any historical rows change, the fingerprint changes and cache should be
    invalidated to avoid stale downstream features.
    """
    if matches_df.empty:
        return "empty"

    cols = [c for c in FINGERPRINT_COLUMNS if c in matches_df.columns]
    if not cols:
        return "no-fingerprint-columns"

    frame = matches_df[cols].copy()

    sort_cols = [c for c in ("id", "date_unix") if c in frame.columns]
    if sort_cols:
        frame = frame.sort_values(sort_cols).reset_index(drop=True)

    row_hashes = pd.util.hash_pandas_object(frame, index=False).values
    return hashlib.sha256(row_hashes.tobytes()).hexdigest()


def read_cache_metadata(path: Path) -> dict[str, Any] | None:
    """Load metadata JSON if present and valid."""
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def validate_cache_metadata(
    metadata: dict[str, Any] | None,
    *,
    feature_version: str,
    source_fingerprint: str,
) -> tuple[bool, str]:
    """Validate metadata against current feature version and source fingerprint."""
    if metadata is None:
        return False, "missing metadata"

    schema_version = metadata.get("schema_version")
    if schema_version != CACHE_METADATA_SCHEMA_VERSION:
        return False, f"metadata schema {schema_version!r} != {CACHE_METADATA_SCHEMA_VERSION!r}"

    cached_feature_version = metadata.get("feature_version")
    if cached_feature_version != feature_version:
        return False, f"feature version {cached_feature_version!r} != {feature_version!r}"

    cached_fingerprint = metadata.get("source_fingerprint")
    if cached_fingerprint != source_fingerprint:
        return False, "source data changed"

    return True, "ok"


def write_cache_metadata(
    path: Path,
    *,
    feature_version: str,
    source_fingerprint: str,
    match_count: int,
) -> None:
    """Persist cache metadata for future validation."""
    metadata = {
        "schema_version": CACHE_METADATA_SCHEMA_VERSION,
        "feature_version": feature_version,
        "source_fingerprint": source_fingerprint,
        "match_count": int(match_count),
    }
    with open(path, "w") as f:
        json.dump(metadata, f, indent=2)
