#!/usr/bin/env python3
"""
Download all available league data from FootyStats API.
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.footystats_client import FootyStatsClient
from data.data_processor import DataProcessor


def main():
    print("=" * 60)
    print("BETBOT - FULL DATA DOWNLOAD")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    client = FootyStatsClient()
    processor = DataProcessor()
    processor.init_database()

    # Test connection
    print("1. Testing API connection...")
    if not client.test_connection():
        print("   ✗ Connection failed!")
        return
    print("   ✓ Connected")

    # Get chosen leagues
    print("\n2. Fetching your chosen leagues...")
    response = client.get_league_list(chosen_leagues_only=True)

    if isinstance(response, dict) and "data" in response:
        leagues = response["data"]
    else:
        leagues = response

    if not leagues:
        print("   ✗ No leagues found! Cache may not be ready yet.")
        print("   Wait 30 minutes after selecting leagues and try again.")
        return

    print(f"   ✓ Found {len(leagues)} leagues")

    # Collect all season IDs
    print("\n3. Collecting seasons...")
    all_seasons = []
    for league in leagues:
        league_name = league.get("name", "Unknown")
        country = league.get("country", "")
        seasons = league.get("season", [])

        if isinstance(seasons, list):
            for s in seasons:
                all_seasons.append({
                    "season_id": s["id"],
                    "year": s.get("year", "Unknown"),
                    "league": league_name,
                    "country": country
                })
        elif seasons:
            all_seasons.append({
                "season_id": seasons,
                "year": "Current",
                "league": league_name,
                "country": country
            })

    print(f"   ✓ Found {len(all_seasons)} seasons to download")

    # Download matches for each season
    print("\n4. Downloading match data...")
    print("-" * 60)

    downloaded = 0
    failed = 0
    total_matches = 0

    for i, season in enumerate(all_seasons):
        season_id = season["season_id"]
        progress = f"[{i+1}/{len(all_seasons)}]"

        try:
            # Get matches
            response = client.get_league_matches(season_id)

            if isinstance(response, dict) and "data" in response:
                matches = response["data"]
            else:
                matches = response if isinstance(response, list) else []

            if not matches:
                print(f"{progress} {season['country']} {season['league']} {season['year']}: No matches")
                continue

            # Process and save
            df = processor.process_matches(matches, season_id)

            # Check if already in database (avoid duplicates)
            existing = processor.load_matches(season_id)
            if len(existing) > 0:
                print(f"{progress} {season['country']} {season['league']} {season['year']}: Already in DB ({len(existing)} matches)")
                continue

            processor.save_matches(df)
            downloaded += 1
            total_matches += len(matches)
            print(f"{progress} {season['country']} {season['league']} {season['year']}: ✓ {len(matches)} matches")

        except Exception as e:
            failed += 1
            error_msg = str(e)
            print(f"{progress} {season['country']} {season['league']} {season['year']}: ✗ {error_msg}")

    # Summary
    print()
    print("=" * 60)
    print("DOWNLOAD COMPLETE")
    print("=" * 60)
    print(f"  Seasons downloaded: {downloaded}")
    print(f"  Seasons failed: {failed}")
    print(f"  Total matches: {total_matches}")
    print(f"  Database: {processor.db_path}")
    print()

    # Show database stats
    all_matches = processor.load_matches()
    print(f"Database now contains {len(all_matches)} matches")

    if len(all_matches) > 0:
        print(f"  Seasons: {all_matches['season'].nunique()}")
        print(f"  Teams: {all_matches['home_team'].nunique()}")
        print(f"  Date range: {all_matches['date_unix'].min()} - {all_matches['date_unix'].max()}")


if __name__ == "__main__":
    main()
