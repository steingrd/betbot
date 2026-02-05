#!/usr/bin/env python3
"""
Data Download Script

Downloads historical match data from FootyStats API and stores locally.
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.footystats_client import FootyStatsClient


def download_league_data(client: FootyStatsClient, season_id: int, output_dir: Path) -> dict:
    """Download all data for a league season"""

    print(f"  Downloading season {season_id}...")

    # Get season info
    try:
        season_info = client.get_league_season(season_id)
    except Exception as e:
        print(f"    Failed to get season info: {e}")
        return None

    # Get matches
    try:
        matches = client.get_league_matches(season_id)
    except Exception as e:
        print(f"    Failed to get matches: {e}")
        matches = []

    # Get table
    try:
        table = client.get_league_table(season_id)
    except Exception as e:
        print(f"    Failed to get table: {e}")
        table = []

    # Combine into one object
    data = {
        "season_id": season_id,
        "downloaded_at": datetime.now().isoformat(),
        "season_info": season_info,
        "matches": matches,
        "table": table
    }

    # Save to file
    output_file = output_dir / f"season_{season_id}.json"
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    match_count = len(matches.get("data", [])) if isinstance(matches, dict) else len(matches)
    print(f"    ✓ Saved {match_count} matches")

    return data


def main():
    """Main download routine"""

    print("=" * 60)
    print("BetBot Data Downloader")
    print("=" * 60)

    # Initialize client
    client = FootyStatsClient()

    # Test connection
    print("\n1. Testing API connection...")
    if not client.test_connection():
        print("   ✗ Connection failed! Check your API key in .env")
        sys.exit(1)
    print("   ✓ Connected")

    # Get available leagues
    print("\n2. Fetching available leagues...")
    leagues_response = client.get_league_list()

    # Handle response format
    if isinstance(leagues_response, dict) and "data" in leagues_response:
        leagues = leagues_response["data"]
    else:
        leagues = leagues_response

    print(f"   Found {len(leagues)} leagues")

    # Output directory
    output_dir = Path(__file__).parent.parent / "data" / "raw" / "seasons"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Download data for each league
    print("\n3. Downloading league data...")

    downloaded = 0
    failed = 0

    for league in tqdm(leagues, desc="Leagues"):
        league_name = league.get("name", "Unknown")
        country = league.get("country", "Unknown")

        # Get season IDs for this league
        season_ids = []
        if "season" in league:
            # Current season
            season_ids.append(league["season"])

        # Some leagues have historical seasons listed
        if "seasons" in league:
            season_ids.extend(league["seasons"])

        for season_id in season_ids:
            try:
                download_league_data(client, season_id, output_dir)
                downloaded += 1
            except Exception as e:
                print(f"   Failed {league_name}: {e}")
                failed += 1

    print("\n" + "=" * 60)
    print(f"Download complete!")
    print(f"  ✓ Downloaded: {downloaded} seasons")
    print(f"  ✗ Failed: {failed} seasons")
    print(f"  Data saved to: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
