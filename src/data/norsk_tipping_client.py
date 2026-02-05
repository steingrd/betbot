"""
Norsk Tipping Oddsen API Client

Henter odds og kampinformasjon fra Norsk Tipping sine APIer:
- OddsenGameInfo API: Sporter, markeder og oddser
- PoolGamesSportInfo API: Tipping-kuponger med kamper

API-dokumentasjon: https://api-portal.norsk-tipping.no/docs/oddsen-shared-api-1
"""

import json
import time
import re
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import requests


@dataclass
class NorskTippingMatch:
    """En fotballkamp med odds fra Norsk Tipping"""
    match_id: str
    home_team: str
    away_team: str
    league: str
    kickoff: datetime
    home_win_probability: Optional[float] = None  # Som prosent (0-100)
    draw_probability: Optional[float] = None
    away_win_probability: Optional[float] = None
    source: str = "norsk_tipping"

    # Alternative lagnavn for matching
    home_team_aliases: List[str] = field(default_factory=list)
    away_team_aliases: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Generer aliases basert på lagnavnene"""
        self.home_team_aliases = self._generate_aliases(self.home_team)
        self.away_team_aliases = self._generate_aliases(self.away_team)

    def _generate_aliases(self, team_name: str) -> List[str]:
        """Generer alternative versjoner av et lagnavn for bedre matching"""
        aliases = [team_name]

        # Fjern vanlige suffikser
        for suffix in [" FC", " AFC", " United", " City"]:
            if team_name.endswith(suffix):
                aliases.append(team_name[:-len(suffix)])

        # Legg til vanlige varianter
        name_mappings = {
            "Newcastle": ["Newcastle United", "Newcastle Utd"],
            "Manchester City": ["Man City", "Man. City"],
            "Manchester United": ["Man United", "Man. United", "Man Utd"],
            "Tottenham": ["Tottenham Hotspur", "Spurs"],
            "Bayern Munchen": ["Bayern Munich", "FC Bayern", "Bayern"],
            "Bayern München": ["Bayern Munich", "FC Bayern", "Bayern"],
            "Juventus": ["Juve"],
            "Liverpool": ["Liverpool FC"],
            "Arsenal": ["Arsenal FC"],
            "Chelsea": ["Chelsea FC"],
            "Nottingham F": ["Nottingham Forest", "Nott'm Forest"],
            "Wolverhampton": ["Wolves", "Wolverhampton Wanderers"],
            "Brighton": ["Brighton & Hove Albion", "Brighton and Hove Albion"],
            "Crystal Palace": ["C. Palace"],
            "West Ham": ["West Ham United", "West Ham Utd"],
            "Aston Villa": ["A. Villa"],
            "Brentford": ["Brentford FC"],
            "Bournemouth": ["AFC Bournemouth"],
            "Everton": ["Everton FC"],
            "Fulham": ["Fulham FC"],
            "Burnley": ["Burnley FC"],
            "Sunderland": ["Sunderland AFC"],
            "TSG 1899 Hoffenheim": ["Hoffenheim", "TSG Hoffenheim"],
            "1. FC Köln": ["FC Koln", "Koln", "Cologne"],
            "RB Leipzig": ["Leipzig", "Red Bull Leipzig"],
        }

        for key, values in name_mappings.items():
            if key.lower() in team_name.lower():
                aliases.extend(values)
            for val in values:
                if val.lower() == team_name.lower():
                    aliases.append(key)

        return list(set(aliases))

    def matches_team(self, team_name: str, side: str = "home") -> bool:
        """Sjekk om et lagnavn matcher hjemme- eller bortelaget"""
        aliases = self.home_team_aliases if side == "home" else self.away_team_aliases
        team_lower = team_name.lower()

        for alias in aliases:
            if alias.lower() == team_lower:
                return True
            # Fuzzy match: sjekk om aliasene er tilstrekkelig like
            if self._fuzzy_match(alias.lower(), team_lower):
                return True

        return False

    def _fuzzy_match(self, a: str, b: str) -> bool:
        """Enkel fuzzy matching av to strenger"""
        # Direkte match
        if a == b:
            return True
        # En er substring av den andre
        if a in b or b in a:
            return True
        # Fjern vanlige prefikser/suffikser og sammenlign
        for word in ["fc", "afc", "united", "city"]:
            a_clean = a.replace(word, "").strip()
            b_clean = b.replace(word, "").strip()
            if a_clean == b_clean:
                return True
        return False

    def to_dict(self) -> dict:
        """Konverter til dictionary"""
        return {
            "match_id": self.match_id,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "league": self.league,
            "kickoff": self.kickoff.isoformat(),
            "home_win_probability": self.home_win_probability,
            "draw_probability": self.draw_probability,
            "away_win_probability": self.away_win_probability,
            "source": self.source,
        }


class NorskTippingClient:
    """Klient for Norsk Tipping Oddsen API"""

    BASE_URL = "https://api.norsk-tipping.no"

    def __init__(self, cache_dir: Optional[Path] = None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; BetBot/1.0)",
            "Accept": "application/json",
        })

        # Cache directory
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            self.cache_dir = Path(__file__).parent.parent.parent / "data" / "raw" / "norsk_tipping_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # sekund mellom requests

    def _rate_limit(self):
        """Sikre at vi ikke oversender API-et"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def _get_cache_path(self, endpoint: str) -> Path:
        """Generer cache-filsti"""
        safe_endpoint = endpoint.replace("/", "_").replace("?", "_").replace("&", "_")
        return self.cache_dir / f"{safe_endpoint}.json"

    def _request(self, endpoint: str, use_cache: bool = True, cache_hours: int = 1) -> Optional[dict]:
        """Gjor en API-request med caching"""
        cache_path = self._get_cache_path(endpoint)

        # Sjekk cache
        if use_cache and cache_path.exists():
            try:
                with open(cache_path, "r") as f:
                    cached = json.load(f)
                    cached_time = datetime.fromisoformat(cached["_cached_at"])
                    if (datetime.now() - cached_time).total_seconds() < cache_hours * 3600:
                        return cached.get("data")
            except (json.JSONDecodeError, KeyError):
                pass

        # Rate limit
        self._rate_limit()

        # Gjor request
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            response = self.session.get(url, timeout=30)

            # 204 No Content betyr ingen data tilgjengelig
            if response.status_code == 204:
                return None

            if response.status_code != 200:
                print(f"API error {response.status_code}: {response.text}")
                return None

            data = response.json()

            # Cache responsen
            if use_cache:
                cache_data = {
                    "_cached_at": datetime.now().isoformat(),
                    "data": data
                }
                with open(cache_path, "w") as f:
                    json.dump(cache_data, f)

            return data

        except requests.RequestException as e:
            print(f"Request error: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return None

    def get_sports(self) -> List[dict]:
        """Hent liste over tilgjengelige sporter"""
        data = self._request("OddsenGameInfo/v1/api/sports")
        if data and "sports" in data:
            return data["sports"]
        return []

    def get_football_sport_id(self) -> Optional[str]:
        """Finn sport-ID for fotball"""
        sports = self.get_sports()
        for sport in sports:
            if sport.get("sportName") == "Fotball":
                return sport.get("sportNavigationId")
        return None

    def get_markets(self, sport_id: str) -> Optional[dict]:
        """Hent markeder for en sport"""
        return self._request(f"OddsenGameInfo/v1/api/markets/{sport_id}")

    def get_events_for_date(self, target_date: date) -> Optional[dict]:
        """Hent hendelser for en spesifikk dato"""
        date_str = target_date.strftime("%Y-%m-%d")
        return self._request(f"OddsenGameInfo/v1/api/events/{date_str}")

    def get_todays_events(self) -> Optional[dict]:
        """Hent dagens hendelser"""
        return self._request("OddsenGameInfo/v1/api/events/today", use_cache=False)

    def get_tipping_matches(self) -> List[NorskTippingMatch]:
        """
        Hent kamper fra Tipping API (pool-spill).
        Dette API-et har alltid data tilgjengelig med kommende kamper.
        """
        data = self._request("PoolGamesSportInfo/v1/api/tipping/live-info", cache_hours=2)

        if not data or "gameDays" not in data:
            return []

        matches = []

        for game_day in data["gameDays"]:
            if "game" not in game_day or "matches" not in game_day["game"]:
                continue

            game = game_day["game"]
            tips = game.get("tips", {})

            for idx, match_data in enumerate(game["matches"]):
                try:
                    # Parse kickoff-tid
                    kickoff_str = match_data.get("date", "")
                    kickoff = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))

                    # Hent sannsynligheter fra tips (expert eller peoples)
                    fulltime_tips = tips.get("fullTime", {})
                    expert_tips = fulltime_tips.get("expert", [])
                    peoples_tips = fulltime_tips.get("peoples", [])

                    home_prob = None
                    draw_prob = None
                    away_prob = None

                    # Bruk expert tips hvis tilgjengelig, ellers peoples
                    if idx < len(expert_tips):
                        tip = expert_tips[idx]
                        home_prob = tip.get("home")
                        draw_prob = tip.get("draw")
                        away_prob = tip.get("away")
                    elif idx < len(peoples_tips):
                        tip = peoples_tips[idx]
                        home_prob = tip.get("home")
                        draw_prob = tip.get("draw")
                        away_prob = tip.get("away")

                    # Hent lagnavn
                    teams = match_data.get("teams", {})
                    home_team = teams.get("home", {}).get("webName", "Unknown")
                    away_team = teams.get("away", {}).get("webName", "Unknown")

                    # Hent liga
                    arrangement = match_data.get("arrangement", {})
                    league = arrangement.get("name", "Unknown")

                    match = NorskTippingMatch(
                        match_id=str(match_data.get("gameEngineEventId", f"tipping_{idx}")),
                        home_team=home_team,
                        away_team=away_team,
                        league=league,
                        kickoff=kickoff,
                        home_win_probability=home_prob,
                        draw_probability=draw_prob,
                        away_win_probability=away_prob,
                        source="norsk_tipping_tipping",
                    )
                    matches.append(match)

                except Exception as e:
                    print(f"Error parsing match: {e}")
                    continue

        return matches

    def get_upcoming_football_matches(self) -> List[NorskTippingMatch]:
        """
        Hent kommende fotballkamper med odds.

        Prover forst OddsenGameInfo API, faller tilbake til Tipping hvis tomt.
        """
        matches = []

        # Prov OddsenGameInfo API for de neste 7 dagene
        football_id = self.get_football_sport_id()
        if football_id:
            markets = self.get_markets(football_id)
            if markets:
                # Parse markets data til NorskTippingMatch objekter
                # (Struktur avhenger av faktisk API-respons)
                pass

        # Prov ogsaa hendelser for de neste dagene
        for days_ahead in range(7):
            target_date = date.today() + timedelta(days=days_ahead)
            events = self.get_events_for_date(target_date)
            if events:
                # Parse events til NorskTippingMatch objekter
                pass

        # Hvis ingen data fra OddsenGameInfo, bruk Tipping
        if not matches:
            matches = self.get_tipping_matches()

        return matches

    def get_football_matches_for_date(self, target_date: date) -> List[NorskTippingMatch]:
        """Hent fotballkamper for en spesifikk dato"""
        all_matches = self.get_upcoming_football_matches()
        return [
            m for m in all_matches
            if m.kickoff.date() == target_date
        ]

    def get_todays_football_matches(self) -> List[NorskTippingMatch]:
        """Hent dagens fotballkamper"""
        return self.get_football_matches_for_date(date.today())

    def find_matching_match(
        self,
        home_team: str,
        away_team: str,
        matches: Optional[List[NorskTippingMatch]] = None
    ) -> Optional[NorskTippingMatch]:
        """
        Finn en kamp som matcher gitte lagnavn.
        Hanter at navnene kan vaere forskjellige fra FootyStats.
        """
        if matches is None:
            matches = self.get_upcoming_football_matches()

        for match in matches:
            if match.matches_team(home_team, "home") and match.matches_team(away_team, "away"):
                return match

        return None


# Quick test
if __name__ == "__main__":
    client = NorskTippingClient()

    print("Norsk Tipping API Test")
    print("=" * 50)

    # Test 1: Hent sporter
    print("\n1. Tilgjengelige sporter:")
    sports = client.get_sports()
    for sport in sports[:5]:
        print(f"   - {sport.get('sportName')} (ID: {sport.get('sportNavigationId')}, {sport.get('numberOfMarkets')} markeder)")

    # Test 2: Hent kommende kamper
    print("\n2. Kommende fotballkamper:")
    matches = client.get_upcoming_football_matches()
    print(f"   Fant {len(matches)} kamper")

    for match in matches[:10]:
        prob_str = ""
        if match.home_win_probability:
            prob_str = f" (H:{match.home_win_probability}% D:{match.draw_probability}% B:{match.away_win_probability}%)"
        print(f"   - {match.kickoff.strftime('%Y-%m-%d %H:%M')}: {match.home_team} vs {match.away_team} [{match.league}]{prob_str}")

    # Test 3: Matching
    print("\n3. Lagnavnmatching test:")
    test_match = client.find_matching_match("Newcastle United", "Brentford FC", matches)
    if test_match:
        print(f"   Fant match: {test_match.home_team} vs {test_match.away_team}")
    else:
        print("   Ingen match funnet")
