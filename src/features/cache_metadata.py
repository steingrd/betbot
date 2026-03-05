"""
Feature cache metadata utilities.

Keeps feature caches safe by binding them to:
- Feature-engine version
- Source match data fingerprint (per-match for incremental support)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


CACHE_METADATA_SCHEMA_VERSION = 2

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


def compute_per_match_fingerprints(matches_df: pd.DataFrame) -> dict[str, str]:
    """
    Compute a per-match fingerprint dict: {match_id: hash}.

    Used for incremental cache validation — only regenerate features for
    matches whose source data has changed or are new.
    """
    if matches_df.empty:
        return {}

    cols = [c for c in FINGERPRINT_COLUMNS if c in matches_df.columns]
    if not cols:
        return {}

    frame = matches_df[cols].copy()
    row_hashes = pd.util.hash_pandas_object(frame, index=False)

    result = {}
    for idx, match_id in enumerate(matches_df["id"].values):
        result[str(int(match_id))] = format(row_hashes.iloc[idx], "x")
    return result


def compute_cache_diff(
    cached_fingerprints: dict[str, str],
    current_fingerprints: dict[str, str],
) -> tuple[set[int], set[int]]:
    """
    Compare cached vs current per-match fingerprints.

    Returns:
        (skip_ids, changed_ids) where:
        - skip_ids: match IDs with unchanged data — reuse cached features
        - changed_ids: match IDs whose source data changed — must regenerate

    New matches (in current but not cached) are neither in skip nor changed;
    they will be computed by the feature generator as normal.

    Note: If any existing match's data changed, we must invalidate ALL cached
    features, because form/position features for later matches depend on
    earlier match results.
    """
    cached_keys = set(cached_fingerprints.keys())
    current_keys = set(current_fingerprints.keys())

    # Matches in both old and new
    common = cached_keys & current_keys

    # Check if any existing match data changed
    changed_ids = {
        int(mid) for mid in common
        if cached_fingerprints[mid] != current_fingerprints[mid]
    }

    if changed_ids:
        # Existing data changed — can't trust any cached features because
        # form/position features cascade from earlier matches
        return set(), changed_ids

    # No existing data changed — safe to reuse all cached features
    skip_ids = {int(mid) for mid in common}
    return skip_ids, set()


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
) -> tuple[bool, str]:
    """Validate metadata schema version and feature version."""
    if metadata is None:
        return False, "missing metadata"

    schema_version = metadata.get("schema_version")
    if schema_version != CACHE_METADATA_SCHEMA_VERSION:
        return False, f"metadata schema {schema_version!r} != {CACHE_METADATA_SCHEMA_VERSION!r}"

    cached_feature_version = metadata.get("feature_version")
    if cached_feature_version != feature_version:
        return False, f"feature version {cached_feature_version!r} != {feature_version!r}"

    return True, "ok"


def write_cache_metadata(
    path: Path,
    *,
    feature_version: str,
    match_fingerprints: dict[str, str],
    match_count: int,
) -> None:
    """Persist cache metadata for future validation."""
    metadata = {
        "schema_version": CACHE_METADATA_SCHEMA_VERSION,
        "feature_version": feature_version,
        "match_fingerprints": match_fingerprints,
        "match_count": int(match_count),
    }
    with open(path, "w") as f:
        json.dump(metadata, f, indent=2)
