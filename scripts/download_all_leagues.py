#!/usr/bin/env python3
"""
Download all available league data from FootyStats API.

Saves both match data and season metadata for proper per-league holdout splits.
By default, skips finished seasons already in the database. Use --full to re-download everything.
"""

import argparse
import sys
import time
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def stable_league_id(country: str, league_name: str) -> int:
    """Generate a stable league ID from country and league name using MD5."""
    key = f"{country}|{league_name}".encode('utf-8')
    return int(hashlib.md5(key).hexdigest()[:8], 16)

from data.footystats_client import FootyStatsClient
from data.data_processor import DataProcessor


def main(full: bool = False):
    print("=" * 60)
    print("BETBOT - DATA DOWNLOAD" + (" (FULL)" if full else ""))
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

    # Collect all season info with league metadata
    # Note: FootyStats API doesn't provide league_id, so we generate one from country+name
    print("\n3. Collecting seasons with league metadata...")
    all_seasons = []
    league_id_map = {}  # (country, name) -> generated_id

    for league in leagues:
        league_name = league.get("name", "Unknown")
        country = league.get("country", "")
        seasons = league.get("season", [])

        # Generate stable league_id from country + name (MD5-based, consistent across runs)
        league_key = (country, league_name)
        if league_key not in league_id_map:
            league_id_map[league_key] = stable_league_id(country, league_name)
        league_id = league_id_map[league_key]

        if isinstance(seasons, list):
            for s in seasons:
                all_seasons.append({
                    "season_id": s["id"],
                    "league_id": league_id,
                    "league_name": league_name,
                    "country": country,
                    "year": s.get("year", "Unknown"),
                })
        elif seasons:
            all_seasons.append({
                "season_id": seasons,
                "league_id": league_id,
                "league_name": league_name,
                "country": country,
                "year": "Current",
            })

    print(f"   ✓ Found {len(all_seasons)} seasons total")

    # Filter out finished seasons unless --full
    if not full:
        conn = sqlite3.connect(str(processor.db_path))
        rows = conn.execute("""
            SELECT s.id, s.end_date, COUNT(m.id) as match_count
            FROM seasons s
            LEFT JOIN matches m ON s.id = m.season_id
            GROUP BY s.id
        """).fetchall()
        conn.close()

        known = {r[0]: (r[1], r[2]) for r in rows}
        now = time.time()
        grace_period = 30 * 86400  # 30 days
        filtered = []
        skipped_count = 0

        for s in all_seasons:
            sid = s["season_id"]
            if sid not in known:
                filtered.append(s)
            elif known[sid][1] == 0:
                filtered.append(s)
            elif known[sid][0] is None:
                filtered.append(s)
            elif known[sid][0] + grace_period > now:
                filtered.append(s)
            else:
                skipped_count += 1

        if skipped_count > 0:
            print(f"\n   Hopper over {skipped_count} ferdige sesonger (bruk --full for aa laste alt)")
        all_seasons = filtered

    print(f"   {len(all_seasons)} sesonger aa laste ned")

    # Group seasons by league for display
    leagues_found = {}
    for s in all_seasons:
        key = f"{s['country']} {s['league_name']}"
        if key not in leagues_found:
            leagues_found[key] = []
        leagues_found[key].append(s["year"])

    print("\n   Leagues and seasons:")
    for league, years in sorted(leagues_found.items()):
        print(f"     {league}: {', '.join(str(y) for y in years)}")

    # Download matches for each season
    print("\n4. Downloading match data and saving metadata...")
    print("-" * 60)

    downloaded = 0
    failed = 0
    total_matches = 0

    def is_active_season(proc, sid):
        """Check if a season is still active (end_date in the future or NULL)."""
        conn = sqlite3.connect(str(proc.db_path))
        row = conn.execute("SELECT end_date FROM seasons WHERE id = ?", (sid,)).fetchone()
        conn.close()
        if row is None or row[0] is None:
            return True
        return row[0] > time.time()

    for i, season in enumerate(all_seasons):
        season_id = season["season_id"]
        league_id = season["league_id"]
        progress = f"[{i+1}/{len(all_seasons)}]"

        try:
            # Save season metadata first
            processor.save_season(
                season_id=season_id,
                league_id=league_id,
                league_name=season["league_name"],
                country=season["country"],
                year=season["year"],
                season_label=f"{season['country']} {season['league_name']} {season['year']}"
            )

            # For active seasons, bypass cache to get fresh data
            active = is_active_season(processor, season_id)
            use_cache = not active

            # Get matches
            response = client.get_league_matches(season_id, use_cache=use_cache)

            if isinstance(response, dict) and "data" in response:
                matches = response["data"]
            else:
                matches = response if isinstance(response, list) else []

            if not matches:
                print(f"{progress} {season['country']} {season['league_name']} {season['year']}: No matches")
                continue

            # Remove any previously saved incomplete matches for this season
            processor.delete_incomplete_matches(season_id=season_id)

            # Process and save with league_id (upsert updates existing matches)
            df = processor.process_matches(matches, season_id, league_id=league_id)
            processor.save_matches(df)

            # Update season start/end dates
            if len(df) > 0:
                start_date = int(df["date_unix"].min())
                end_date = int(df["date_unix"].max())
                processor.update_season_dates(season_id, start_date, end_date)

            tag = "(fresh)" if not use_cache else "(cached)"
            downloaded += 1
            total_matches += len(matches)
            print(f"{progress} {season['country']} {season['league_name']} {season['year']}: ✓ {len(matches)} matches {tag}")

        except Exception as e:
            failed += 1
            error_msg = str(e)
            print(f"{progress} {season['country']} {season['league_name']} {season['year']}: ✗ {error_msg}")

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
    seasons_df = processor.load_seasons()

    print(f"Database now contains:")
    print(f"  {len(all_matches)} matches")
    print(f"  {len(seasons_df)} seasons")

    if len(seasons_df) > 0:
        print(f"\nSeasons by league:")
        by_league = seasons_df.groupby(["country", "league_name"]).agg(
            seasons=("id", "count"),
            years=("year", lambda x: ", ".join(str(y) for y in sorted(x)))
        ).reset_index()
        for _, row in by_league.iterrows():
            print(f"  {row['country']} {row['league_name']}: {row['seasons']} seasons ({row['years']})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download league data from FootyStats")
    parser.add_argument("--full", action="store_true", help="Re-download all seasons (default: skip finished)")
    args = parser.parse_args()
    main(full=args.full)
