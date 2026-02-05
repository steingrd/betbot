#!/usr/bin/env python3
"""
Quick API test script - run this first to verify your API key works.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.footystats_client import FootyStatsClient


def main():
    print("FootyStats API Test")
    print("-" * 40)

    client = FootyStatsClient()
    print(f"Using API key: {client.api_key[:8]}..." if len(client.api_key) > 8 else f"Using API key: {client.api_key}")

    # Test 1: Connection
    print("\n1. Testing connection...")
    if client.test_connection():
        print("   ✓ Connection OK")
    else:
        print("   ✗ Connection FAILED")
        return

    # Test 2: Get leagues
    print("\n2. Fetching leagues...")
    try:
        leagues = client.get_league_list()
        if isinstance(leagues, dict) and "data" in leagues:
            leagues = leagues["data"]
        print(f"   ✓ Found {len(leagues)} leagues")

        print("\n   Sample leagues:")
        for league in leagues[:10]:
            print(f"   - {league.get('name')} ({league.get('country')}) - Season ID: {league.get('season')}")

    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return

    # Test 3: Get matches for one league
    print("\n3. Fetching sample matches...")
    if leagues:
        sample_league = leagues[0]
        season_id = sample_league.get("season")
        if season_id:
            try:
                matches = client.get_league_matches(season_id)
                if isinstance(matches, dict) and "data" in matches:
                    matches = matches["data"]
                print(f"   ✓ Found {len(matches)} matches for {sample_league.get('name')}")

                if matches:
                    sample_match = matches[0]
                    print(f"\n   Sample match data fields:")
                    for key in list(sample_match.keys())[:15]:
                        print(f"   - {key}: {sample_match.get(key)}")

            except Exception as e:
                print(f"   ✗ Failed: {e}")

    print("\n" + "-" * 40)
    print("API test complete!")


if __name__ == "__main__":
    main()
