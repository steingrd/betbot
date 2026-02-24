"""
FootyStats API Client

Handles all communication with the FootyStats API (api.football-data-api.com)
"""

import os
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
import requests
from dotenv import load_dotenv

load_dotenv()


class FootyStatsClient:
    """Client for FootyStats API"""

    BASE_URL = "https://api.football-data-api.com"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FOOTYSTATS_API_KEY", "example")
        self.session = requests.Session()
        self.request_count = 0
        self.last_request_time = 0

        # Rate limiting: max 1800 requests/hour for hobby tier = 0.5 req/sec
        self.min_request_interval = 2.0  # seconds between requests (conservative)

        # Cache directory
        self.cache_dir = Path(__file__).parent.parent.parent / "data" / "raw" / "api_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _rate_limit(self):
        """Ensure we don't exceed rate limits"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def _get_cache_path(self, endpoint: str, params: dict) -> Path:
        """Generate cache file path for a request"""
        # Create a unique filename from endpoint and params
        param_str = "_".join(f"{k}={v}" for k, v in sorted(params.items()) if k != "key")
        safe_endpoint = endpoint.replace("/", "_")
        filename = f"{safe_endpoint}_{param_str}.json"
        return self.cache_dir / filename

    def _request(self, endpoint: str, params: Optional[dict] = None, use_cache: bool = True) -> dict:
        """Make an API request with caching and rate limiting"""
        params = params or {}
        params["key"] = self.api_key

        # Check cache first
        cache_path = self._get_cache_path(endpoint, params)
        if use_cache and cache_path.exists():
            with open(cache_path, "r") as f:
                cached = json.load(f)
                # Cache valid for 24 hours for historical data
                if cached.get("_cached_at"):
                    cached_time = datetime.fromisoformat(cached["_cached_at"])
                    if (datetime.now() - cached_time).total_seconds() < 86400:
                        return cached["data"]

        # Rate limit
        self._rate_limit()

        # Make request
        url = f"{self.BASE_URL}/{endpoint}"
        response = self.session.get(url, params=params)
        self.request_count += 1

        if response.status_code != 200:
            raise Exception(f"API error {response.status_code}: {response.text}")

        data = response.json()

        # Cache the response
        if use_cache:
            cache_data = {
                "_cached_at": datetime.now().isoformat(),
                "data": data
            }
            with open(cache_path, "w") as f:
                json.dump(cache_data, f)

        return data

    def test_connection(self) -> bool:
        """Test if API connection works"""
        try:
            result = self._request("test-call", use_cache=False)
            return result.get("success", False)
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False

    def get_league_list(self, chosen_leagues_only: bool = True) -> list:
        """Get list of available leagues"""
        params = {}
        if chosen_leagues_only:
            params["chosen_leagues_only"] = "true"
        return self._request("league-list", params)

    def get_league_matches(self, season_id: int, use_cache: bool = True) -> list:
        """Get all matches for a season"""
        return self._request("league-matches", {"season_id": season_id}, use_cache=use_cache)

    def get_league_season(self, season_id: int) -> dict:
        """Get season details including stats"""
        return self._request("league-season", {"season_id": season_id})

    def get_league_table(self, season_id: int) -> list:
        """Get league table/standings"""
        return self._request("league-tables", {"season_id": season_id})

    def get_team(self, team_id: int, season_id: Optional[int] = None) -> dict:
        """Get team details and stats"""
        params = {"team_id": team_id}
        if season_id:
            params["season_id"] = season_id
        return self._request("team", params)

    def get_match(self, match_id: int) -> dict:
        """Get detailed match data"""
        return self._request("match", {"match_id": match_id})

    def get_todays_matches(self) -> list:
        """Get today's matches"""
        return self._request("todays-matches", use_cache=False)

    def get_country_list(self) -> list:
        """Get list of countries with leagues"""
        return self._request("country-list")


# Quick test
if __name__ == "__main__":
    client = FootyStatsClient()

    print("Testing API connection...")
    if client.test_connection():
        print("✓ Connection successful!")

        print("\nFetching league list...")
        leagues = client.get_league_list()

        if isinstance(leagues, dict) and "data" in leagues:
            leagues = leagues["data"]

        print(f"Found {len(leagues)} leagues")

        # Show first 5
        for league in leagues[:5]:
            print(f"  - {league.get('name', 'Unknown')} (ID: {league.get('id', 'N/A')})")
    else:
        print("✗ Connection failed - check your API key")
