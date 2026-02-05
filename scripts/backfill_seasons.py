#!/usr/bin/env python3
"""
Backfill season metadata for existing matches.

This script:
1. Fetches league info from FootyStats API
2. Populates the seasons table with league_id, league_name, country
3. Updates season start/end dates from match data
4. Optionally updates league_id in matches table

Run this after upgrading to the new schema if you have existing data.
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.footystats_client import FootyStatsClient
from data.data_processor import DataProcessor


def main():
    print("=" * 60)
    print("BETBOT - BACKFILL SEASON METADATA")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    client = FootyStatsClient()
    processor = DataProcessor()

    # Ensure new schema exists
    processor.init_database()

    # Check existing data
    matches = processor.load_matches()
    if len(matches) == 0:
        print("No matches in database. Run download_all_leagues.py first.")
        return

    print(f"Found {len(matches)} matches in database")
    existing_seasons = matches["season_id"].unique()
    print(f"Found {len(existing_seasons)} unique season_ids")

    # Get league list from API
    print("\nFetching league info from API...")
    response = client.get_league_list(chosen_leagues_only=True)

    if isinstance(response, dict) and "data" in response:
        leagues = response["data"]
    else:
        leagues = response

    if not leagues:
        print("WARNING: Could not fetch leagues from API.")
        print("Will use existing match data to compute season dates only.")
        leagues = []

    # Build season -> league mapping
    # Note: FootyStats API doesn't provide league_id, so we generate one from country+name
    season_info = {}
    league_id_map = {}  # (country, name) -> generated_id

    for league in leagues:
        league_name = league.get("name", "Unknown")
        country = league.get("country", "")
        seasons = league.get("season", [])

        # Generate stable league_id from country + name
        league_key = (country, league_name)
        if league_key not in league_id_map:
            league_id_map[league_key] = hash(league_key) % (10**9)  # Stable hash
        league_id = league_id_map[league_key]

        if isinstance(seasons, list):
            for s in seasons:
                season_info[s["id"]] = {
                    "league_id": league_id,
                    "league_name": league_name,
                    "country": country,
                    "year": s.get("year", "Unknown")
                }
        elif seasons:
            season_info[seasons] = {
                "league_id": league_id,
                "league_name": league_name,
                "country": country,
                "year": "Current"
            }

    print(f"Found info for {len(season_info)} seasons from API")

    # Process each season in database
    print("\nUpdating season metadata...")
    updated = 0
    missing_info = 0

    for season_id in existing_seasons:
        season_matches = matches[matches["season_id"] == season_id]

        # Get date range from matches
        start_date = int(season_matches["date_unix"].min())
        end_date = int(season_matches["date_unix"].max())

        if season_id in season_info:
            info = season_info[season_id]
            processor.save_season(
                season_id=season_id,
                league_id=info["league_id"],
                league_name=info["league_name"],
                country=info["country"],
                year=info["year"],
                season_label=f"{info['country']} {info['league_name']} {info['year']}"
            )
            processor.update_season_dates(season_id, start_date, end_date)
            updated += 1
            print(f"  ✓ Season {season_id}: {info['country']} {info['league_name']} {info['year']} ({len(season_matches)} matches)")
        else:
            # No API info - save with just dates and placeholder info
            processor.save_season(
                season_id=season_id,
                league_id=None,
                league_name="Unknown",
                country="Unknown",
                year=str(datetime.fromtimestamp(start_date).year),
                season_label=f"Season {season_id}"
            )
            processor.update_season_dates(season_id, start_date, end_date)
            missing_info += 1
            print(f"  ? Season {season_id}: No API info ({len(season_matches)} matches)")

    # Summary
    print()
    print("=" * 60)
    print("BACKFILL COMPLETE")
    print("=" * 60)
    print(f"  Seasons updated with full info: {updated}")
    print(f"  Seasons with missing API info: {missing_info}")

    # Verify
    seasons_df = processor.load_seasons()
    print(f"\nSeasons table now contains {len(seasons_df)} records")

    if len(seasons_df) > 0:
        print("\nSeasons by league:")
        by_league = seasons_df.groupby(["country", "league_name"]).size().reset_index(name="count")
        for _, row in by_league.iterrows():
            print(f"  {row['country']} {row['league_name']}: {row['count']} seasons")


if __name__ == "__main__":
    main()
