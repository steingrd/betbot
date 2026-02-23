#!/usr/bin/env python3
"""
Daily Picks - Find value bets for upcoming matches

Combines:
1. Upcoming matches from Norsk Tipping
2. Historical data from FootyStats
3. ML model predictions for Draw and BTTS (profitable markets)
4. Value bet detection

Usage:
    python scripts/daily_picks.py                    # Today's picks
    python scripts/daily_picks.py --date 2026-02-08 # Specific date
    python scripts/daily_picks.py --min-edge 0.08   # Higher edge threshold
    python scripts/daily_picks.py --report          # Save markdown report
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, date
from typing import Optional, List, Dict, Tuple
import json
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.norsk_tipping_client import NorskTippingClient, NorskTippingMatch
from data.data_processor import DataProcessor
from features.feature_engineering import FeatureEngineer
from models.match_predictor import MatchPredictor
from analysis.value_finder import ValueBetFinder


# Team name mapping: NT name -> FootyStats name
TEAM_NAME_MAP = {
    # England
    "wolverhampton": "Wolverhampton Wanderers",
    "wolves": "Wolverhampton Wanderers",
    "brighton": "Brighton & Hove Albion",
    "bournemouth": "AFC Bournemouth",
    "west bromwich": "West Bromwich Albion",
    "west brom": "West Bromwich Albion",
    "tottenham": "Tottenham Hotspur",
    "spurs": "Tottenham Hotspur",
    "newcastle": "Newcastle United",
    "man city": "Manchester City",
    "manchester city": "Manchester City",
    "man united": "Manchester United",
    "manchester united": "Manchester United",
    "nottingham f": "Nottingham Forest",
    "nottingham forest": "Nottingham Forest",
    "nott'm forest": "Nottingham Forest",
    "west ham": "West Ham United",
    "leicester": "Leicester City",
    "leeds": "Leeds United",
    "sheffield united": "Sheffield United",
    "sheffield utd": "Sheffield United",
    "ipswich": "Ipswich Town",
    "luton": "Luton Town",
    # Germany
    "bayern münchen": "Bayern München",
    "bayern munich": "Bayern München",
    "bayern munchen": "Bayern München",
    "rb leipzig": "RB Leipzig",
    "leipzig": "RB Leipzig",
    "1. fc köln": "Köln",
    "fc köln": "Köln",
    "koln": "Köln",
    "cologne": "Köln",
    "hoffenheim": "TSG 1899 Hoffenheim",
    "tsg hoffenheim": "TSG 1899 Hoffenheim",
    "tsg 1899 hoffenheim": "TSG 1899 Hoffenheim",
    "borussia dortmund": "Borussia Dortmund",
    "dortmund": "Borussia Dortmund",
    "bayer leverkusen": "Bayer 04 Leverkusen",
    "leverkusen": "Bayer 04 Leverkusen",
    # Italy
    "inter": "Inter",
    "inter milan": "Inter",
    "ac milan": "AC Milan",
    "milan": "AC Milan",
    "juventus": "Juventus",
    "juve": "Juventus",
    "napoli": "Napoli",
    "roma": "Roma",
    "as roma": "Roma",
    "lazio": "Lazio",
    # Spain
    "real madrid": "Real Madrid",
    "barcelona": "Barcelona",
    "atletico madrid": "Atletico Madrid",
    "atlético madrid": "Atletico Madrid",
    "athletic bilbao": "Athletic Bilbao",
    "real betis": "Real Betis",
    "valencia": "Valencia",
    "sevilla": "Sevilla",
    "villarreal": "Villarreal",
    # France
    "paris saint-germain": "Paris Saint-Germain",
    "psg": "Paris Saint-Germain",
    "marseille": "Marseille",
    "om": "Marseille",
    "lyon": "Lyon",
    "olympique lyon": "Lyon",
    "monaco": "Monaco",
    "as monaco": "Monaco",
    "nice": "Nice",
    "ogc nice": "Nice",
    "lille": "Lille",
}


class DailyPicksFinder:
    """Find daily value bet picks using ML model for Draw and BTTS"""

    def __init__(self, min_edge: float = 0.05, min_odds: float = 1.5, max_odds: float = 10.0):
        self.min_edge = min_edge
        self.min_odds = min_odds
        self.max_odds = max_odds

        self.nt_client = NorskTippingClient()
        self.processor = DataProcessor()
        self.predictor = None
        self.engineer = None
        self.matches_df = None
        self.seasons_df = None
        self.value_finder = ValueBetFinder(min_edge, min_odds, max_odds)

    def load_model(self) -> bool:
        """Load the trained model and historical data"""
        try:
            self.predictor = MatchPredictor()
            self.predictor.load()

            # Load historical data for feature generation
            self.matches_df = self.processor.load_matches()
            self.seasons_df = self.processor.load_seasons()
            self.engineer = FeatureEngineer(self.matches_df)
            return True
        except Exception as e:
            print(f"Could not load model: {e}")
            return False

    def get_upcoming_matches(self, target_date: Optional[date] = None) -> List[NorskTippingMatch]:
        """Get upcoming matches from Norsk Tipping"""
        if target_date:
            return self.nt_client.get_football_matches_for_date(target_date)
        return self.nt_client.get_upcoming_football_matches()

    def convert_nt_probs_to_odds(self, match: NorskTippingMatch) -> Dict[str, float]:
        """Convert Norsk Tipping probabilities to decimal odds"""
        def prob_to_odds(prob):
            if prob <= 0:
                return 0
            return round(100 / prob, 2)

        return {
            "odds_home": prob_to_odds(match.home_win_probability),
            "odds_draw": prob_to_odds(match.draw_probability),
            "odds_away": prob_to_odds(match.away_win_probability),
        }

    def normalize_team_name(self, name: str) -> str:
        """Normalize a team name for matching"""
        name_lower = name.lower().strip()
        if name_lower in TEAM_NAME_MAP:
            return TEAM_NAME_MAP[name_lower]
        return name

    def find_team_in_db(self, nt_name: str) -> Optional[str]:
        """Find a team in our database matching NT name"""
        if self.matches_df is None:
            return None

        # Try direct mapping first
        normalized = self.normalize_team_name(nt_name)

        # Get all unique teams in database
        all_teams = set(self.matches_df["home_team"].unique()) | set(self.matches_df["away_team"].unique())

        # Exact match
        if normalized in all_teams:
            return normalized

        # Case-insensitive match
        name_lower = normalized.lower()
        for team in all_teams:
            if team.lower() == name_lower:
                return team

        # Fuzzy match - check if one contains the other
        for team in all_teams:
            team_lower = team.lower()
            if name_lower in team_lower or team_lower in name_lower:
                return team

        return None

    def compute_features_for_match(
        self, home_team: str, away_team: str, match_date: datetime
    ) -> Optional[pd.DataFrame]:
        """Compute features for an upcoming match using historical data"""
        if self.engineer is None or self.matches_df is None:
            return None

        # Get recent form for both teams
        date_unix = int(match_date.timestamp())

        # Filter to matches before this date
        historical = self.matches_df[self.matches_df["date_unix"] < date_unix].copy()

        if len(historical) == 0:
            return None

        # Get team's recent matches
        home_matches = historical[
            (historical["home_team"] == home_team) | (historical["away_team"] == home_team)
        ].tail(10)

        away_matches = historical[
            (historical["home_team"] == away_team) | (historical["away_team"] == away_team)
        ].tail(10)

        if len(home_matches) < 3 or len(away_matches) < 3:
            return None

        # Compute form features
        home_form = self._compute_form(home_matches, home_team)
        away_form = self._compute_form(away_matches, away_team)

        # Get league draw rate
        recent_all = historical.tail(500)
        league_draw_rate = (recent_all["result"] == "D").mean() if len(recent_all) > 0 else 0.25

        # Build feature row
        features = {
            "match_id": f"upcoming_{home_team}_{away_team}",
            "home_team": home_team,
            "away_team": away_team,
            "game_week": 0,
            "date_unix": date_unix,

            # Home form
            "home_form_ppg": home_form["ppg"],
            "home_form_goals_for": home_form["goals_for"],
            "home_form_goals_against": home_form["goals_against"],
            "home_form_goal_diff": home_form["goal_diff"],
            "home_form_xg": home_form.get("xg", 0),
            "home_venue_ppg": home_form["venue_ppg"],
            "home_venue_goals_for": home_form["venue_goals_for"],
            "home_venue_goals_against": home_form["venue_goals_against"],
            "home_position": home_form.get("position", 10),
            "home_season_points": home_form.get("season_points", 0),
            "home_season_gd": home_form.get("season_gd", 0),

            # Away form
            "away_form_ppg": away_form["ppg"],
            "away_form_goals_for": away_form["goals_for"],
            "away_form_goals_against": away_form["goals_against"],
            "away_form_goal_diff": away_form["goal_diff"],
            "away_form_xg": away_form.get("xg", 0),
            "away_venue_ppg": away_form["venue_ppg"],
            "away_venue_goals_for": away_form["venue_goals_for"],
            "away_venue_goals_against": away_form["venue_goals_against"],
            "away_position": away_form.get("position", 10),
            "away_season_points": away_form.get("season_points", 0),
            "away_season_gd": away_form.get("season_gd", 0),

            # Differences
            "form_ppg_diff": home_form["ppg"] - away_form["ppg"],
            "position_diff": home_form.get("position", 10) - away_form.get("position", 10),
            "xg_diff": home_form.get("xg", 0) - away_form.get("xg", 0),

            # League
            "league_draw_rate": league_draw_rate,

            # H2H (simplified - use 0 if no history)
            "h2h_home_wins": 0,
            "h2h_draws": 0,
            "h2h_away_wins": 0,
            "h2h_total_goals": 0,

            # Pre-match PPG (use form PPG as proxy)
            "home_prematch_ppg": home_form["ppg"],
            "away_prematch_ppg": away_form["ppg"],
            "home_overall_ppg": home_form["ppg"],
            "away_overall_ppg": away_form["ppg"],
            "prematch_ppg_diff": home_form["ppg"] - away_form["ppg"],

            # Pre-match xG
            "home_xg_prematch": home_form.get("xg", 1.3),
            "away_xg_prematch": away_form.get("xg", 1.0),
            "total_xg_prematch": home_form.get("xg", 1.3) + away_form.get("xg", 1.0),
            "xg_prematch_diff": home_form.get("xg", 1.3) - away_form.get("xg", 1.0),

            # Attack quality (use default if not available)
            "home_attack_quality": 0.3,
            "away_attack_quality": 0.3,

            # FootyStats potential (use neutral values)
            "fs_btts_potential": 50,
            "fs_o25_potential": 50,
            "fs_o35_potential": 30,

            # Targets (dummy - not used for prediction)
            "target_result": "D",
            "target_over_25": 0,
            "target_btts": 0,
        }

        return pd.DataFrame([features])

    def _compute_form(self, matches: pd.DataFrame, team: str) -> Dict:
        """Compute form statistics for a team"""
        if len(matches) == 0:
            return {
                "ppg": 1.0, "goals_for": 1.0, "goals_against": 1.0, "goal_diff": 0,
                "xg": 1.0, "venue_ppg": 1.0, "venue_goals_for": 1.0, "venue_goals_against": 1.0
            }

        points = []
        goals_for = []
        goals_against = []
        xg_list = []
        venue_points = []
        venue_gf = []
        venue_ga = []

        for _, m in matches.iterrows():
            is_home = m["home_team"] == team

            if is_home:
                gf = m["home_goals"] if pd.notna(m["home_goals"]) else 0
                ga = m["away_goals"] if pd.notna(m["away_goals"]) else 0
                xg = m["home_xg"] if pd.notna(m.get("home_xg")) else gf
            else:
                gf = m["away_goals"] if pd.notna(m["away_goals"]) else 0
                ga = m["home_goals"] if pd.notna(m["home_goals"]) else 0
                xg = m["away_xg"] if pd.notna(m.get("away_xg")) else gf

            # Calculate points
            if gf > ga:
                pts = 3
            elif gf == ga:
                pts = 1
            else:
                pts = 0

            points.append(pts)
            goals_for.append(gf)
            goals_against.append(ga)
            xg_list.append(xg)

            # Venue-specific
            if is_home:
                venue_points.append(pts)
                venue_gf.append(gf)
                venue_ga.append(ga)

        return {
            "ppg": np.mean(points) if points else 1.0,
            "goals_for": np.mean(goals_for) if goals_for else 1.0,
            "goals_against": np.mean(goals_against) if goals_against else 1.0,
            "goal_diff": np.mean(goals_for) - np.mean(goals_against) if goals_for else 0,
            "xg": np.mean(xg_list) if xg_list else 1.0,
            "venue_ppg": np.mean(venue_points) if venue_points else 1.0,
            "venue_goals_for": np.mean(venue_gf) if venue_gf else 1.0,
            "venue_goals_against": np.mean(venue_ga) if venue_ga else 1.0,
        }

    def find_value_bets(self, matches: List[NorskTippingMatch]) -> List[Dict]:
        """Find value bets using ML model for Draw and BTTS"""

        if not self.predictor or not self.predictor.is_fitted:
            print("Warning: Model not loaded. Using heuristics only.")
            return self._find_value_without_model(matches)

        picks = []

        for match in matches:
            # Try to match teams to our database
            home_db = self.find_team_in_db(match.home_team)
            away_db = self.find_team_in_db(match.away_team)

            match_info = {
                "home_team": match.home_team,
                "away_team": match.away_team,
                "home_team_db": home_db,
                "away_team_db": away_db,
                "league": match.league,
                "kickoff": match.kickoff.strftime("%Y-%m-%d %H:%M") if match.kickoff else "Unknown",
                "nt_home_prob": match.home_win_probability,
                "nt_draw_prob": match.draw_probability,
                "nt_away_prob": match.away_win_probability,
            }

            odds = self.convert_nt_probs_to_odds(match)
            match_info.update(odds)

            # If we can match both teams, use ML model
            if home_db and away_db:
                features = self.compute_features_for_match(home_db, away_db, match.kickoff)

                if features is not None:
                    try:
                        predictions = self.predictor.predict(features)

                        # Extract probabilities
                        model_draw = predictions["prob_D"].iloc[0]
                        model_btts = predictions["prob_btts"].iloc[0]

                        # NT implied probabilities
                        nt_draw_implied = match.draw_probability / 100 if match.draw_probability else 0

                        # Calculate edges
                        draw_edge = model_draw - nt_draw_implied

                        # Check Draw market
                        draw_odds = odds["odds_draw"]
                        if (draw_edge >= self.min_edge and
                            draw_odds >= self.min_odds and
                            draw_odds <= self.max_odds):

                            confidence = "High" if draw_edge >= 0.10 else "Medium" if draw_edge >= 0.07 else "Low"
                            picks.append({
                                **match_info,
                                "market": "Draw",
                                "model_prob": model_draw,
                                "implied_prob": nt_draw_implied,
                                "edge": draw_edge,
                                "confidence": confidence,
                                "source": "ML Model",
                                "reasoning": f"ML-modell: {model_draw:.1%} vs NT: {nt_draw_implied:.1%}"
                            })

                        # BTTS - we don't have NT odds, but show high confidence predictions
                        if model_btts >= 0.55:  # Only show if model is confident
                            picks.append({
                                **match_info,
                                "market": "BTTS",
                                "model_prob": model_btts,
                                "implied_prob": None,  # No NT odds for BTTS
                                "edge": None,
                                "confidence": "High" if model_btts >= 0.65 else "Medium",
                                "source": "ML Model",
                                "reasoning": f"ML-modell: {model_btts:.1%} (ingen NT-odds tilgjengelig)"
                            })

                    except Exception as e:
                        print(f"  Error predicting {match.home_team} vs {match.away_team}: {e}")

        # Sort by edge (Draw first, then BTTS by probability)
        def sort_key(p):
            if p["edge"] is not None:
                return (0, -p["edge"])
            return (1, -p["model_prob"])

        picks.sort(key=sort_key)

        return picks

    def _find_value_without_model(self, matches: List[NorskTippingMatch]) -> List[Dict]:
        """
        Find value bets using historical patterns to adjust Norsk Tipping probabilities.

        Strategy: Apply historical biases to NT probabilities:
        - Home advantage is typically underestimated by ~3-5%
        - Strong favorites (>70%) win more often than priced
        - Away favorites at good odds are often undervalued
        """
        picks = []

        # Historical adjustment factors (based on betting market research)
        HOME_BOOST = 0.03  # Home teams win ~3% more than priced
        FAVORITE_BOOST = 0.05  # Strong favorites (>70%) get extra boost
        AWAY_FAVORITE_BOOST = 0.07  # Away favorites are most undervalued

        for match in matches:
            odds = self.convert_nt_probs_to_odds(match)

            # NT probabilities
            nt_home = match.home_win_probability / 100
            nt_draw = match.draw_probability / 100
            nt_away = match.away_win_probability / 100

            match_info = {
                "home_team": match.home_team,
                "away_team": match.away_team,
                "league": match.league,
                "kickoff": match.kickoff.strftime("%Y-%m-%d %H:%M") if match.kickoff else "Unknown",
                "nt_home_prob": match.home_win_probability,
                "nt_draw_prob": match.draw_probability,
                "nt_away_prob": match.away_win_probability,
                "odds_home": odds["odds_home"],
                "odds_draw": odds["odds_draw"],
                "odds_away": odds["odds_away"],
            }

            # Calculate adjusted probabilities
            # Strategy 1: Home advantage boost
            adj_home = nt_home + HOME_BOOST
            if nt_home >= 0.70:
                adj_home += FAVORITE_BOOST  # Extra boost for strong home favorites

            # Strategy 2: Away favorites get biggest boost (most mispriced market)
            adj_away = nt_away
            if nt_away >= 0.50:  # Away favorite
                adj_away += AWAY_FAVORITE_BOOST
            elif nt_away >= 0.35:  # Slight away favorite or close match
                adj_away += HOME_BOOST

            # Calculate edges
            home_edge = adj_home - nt_home  # Edge vs NT probability
            away_edge = adj_away - nt_away

            # Home picks
            if home_edge >= self.min_edge and odds["odds_home"] >= self.min_odds and odds["odds_home"] <= self.max_odds:
                confidence = "High" if nt_home >= 0.70 else "Medium" if nt_home >= 0.55 else "Low"
                picks.append({
                    **match_info,
                    "market": "Home",
                    "our_prob": adj_home,
                    "implied_prob": nt_home,
                    "edge": home_edge,
                    "confidence": confidence,
                    "reasoning": f"Hjemmefordel + favorittboost ({nt_home:.0%} → {adj_home:.0%})"
                })

            # Away picks (most valuable historically)
            if away_edge >= self.min_edge and odds["odds_away"] >= self.min_odds and odds["odds_away"] <= self.max_odds:
                confidence = "High" if nt_away >= 0.55 else "Medium" if nt_away >= 0.40 else "Low"
                picks.append({
                    **match_info,
                    "market": "Away",
                    "our_prob": adj_away,
                    "implied_prob": nt_away,
                    "edge": away_edge,
                    "confidence": confidence,
                    "reasoning": f"Bortefavoritt undervurdert ({nt_away:.0%} → {adj_away:.0%})"
                })

        # Sort by confidence then edge
        confidence_order = {"High": 0, "Medium": 1, "Low": 2}
        picks.sort(key=lambda x: (confidence_order.get(x["confidence"], 3), -x["edge"]))

        return picks

    def generate_report(self, picks: List[Dict], target_date: Optional[date] = None) -> str:
        """Generate markdown report"""
        date_str = target_date.strftime("%Y-%m-%d") if target_date else datetime.now().strftime("%Y-%m-%d")

        lines = [
            f"# BetBot Daily Picks - {date_str}",
            "",
            f"*Generert: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            "",
            f"**Parametere:** Min edge: {self.min_edge:.0%}, Odds range: {self.min_odds}-{self.max_odds}",
            "",
        ]

        if not picks:
            lines.append("## Ingen value bets funnet")
            lines.append("")
            lines.append("Ingen kamper møtte kriteriene for value bets i dag.")
            return "\n".join(lines)

        lines.append(f"## {len(picks)} Value Bets Funnet")
        lines.append("")

        # Group by confidence
        high_conf = [p for p in picks if p.get("confidence") == "High"]
        med_conf = [p for p in picks if p.get("confidence") == "Medium"]
        low_conf = [p for p in picks if p.get("confidence") == "Low"]

        if high_conf:
            lines.append("### Høy Konfidanse")
            lines.append("")
            for pick in high_conf:
                lines.extend(self._format_pick(pick))

        if med_conf:
            lines.append("### Medium Konfidanse")
            lines.append("")
            for pick in med_conf:
                lines.extend(self._format_pick(pick))

        if low_conf:
            lines.append("### Lav Konfidanse")
            lines.append("")
            for pick in low_conf:
                lines.extend(self._format_pick(pick))

        # Summary
        lines.append("---")
        lines.append("")
        lines.append("## Oppsummering")
        lines.append("")
        lines.append(f"| Metric | Verdi |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Totalt antall picks | {len(picks)} |")
        lines.append(f"| Høy konfidanse | {len(high_conf)} |")
        lines.append(f"| Medium konfidanse | {len(med_conf)} |")
        lines.append(f"| Lav konfidanse | {len(low_conf)} |")
        lines.append(f"| Gjennomsnittlig edge | {sum(p['edge'] for p in picks) / len(picks):.1%} |")
        lines.append(f"| Anbefalt innsats per bet | 10 kr |")
        lines.append(f"| Total innsats | {len(picks) * 10} kr |")
        lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("*Disclaimer: Dette er et eksperimentelt system. Spill ansvarlig.*")

        return "\n".join(lines)

    def _format_pick(self, pick: Dict) -> List[str]:
        """Format a single pick for the report"""
        return [
            f"**{pick['home_team']} vs {pick['away_team']}**",
            f"- Liga: {pick['league']}",
            f"- Avspark: {pick['kickoff']}",
            f"- **Pick: {pick['market']}** @ {pick.get('odds_' + pick['market'].lower(), 'N/A')}",
            f"- Vår sannsynlighet: {pick['our_prob']:.1%}",
            f"- NT sannsynlighet: {pick['nt_' + pick['market'].lower() + '_prob']}%",
            f"- Edge: **{pick['edge']:.1%}**",
            f"- Begrunnelse: {pick['reasoning']}",
            "",
        ]


def main():
    parser = argparse.ArgumentParser(description="Find daily value bet picks")
    parser.add_argument("--date", type=str, help="Target date (YYYY-MM-DD)")
    parser.add_argument("--min-edge", type=float, default=0.05, help="Minimum edge (default: 0.05)")
    parser.add_argument("--report", action="store_true", help="Save markdown report")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--show-matching", action="store_true", help="Show team matching details")
    args = parser.parse_args()

    target_date = None
    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()

    print("=" * 60)
    print("BETBOT DAILY PICKS (ML Model: Draw + BTTS)")
    print("=" * 60)
    print()

    finder = DailyPicksFinder(min_edge=args.min_edge)

    # Try to load model (optional - will work without it)
    print("Loading model and historical data...")
    if finder.load_model():
        print("  ✓ Model loaded")
        print(f"  ✓ {len(finder.matches_df)} historical matches loaded")
    else:
        print("  ⚠ Model not available - using heuristics only")

    # Get upcoming matches
    print("\nFetching upcoming matches from Norsk Tipping...")
    matches = finder.get_upcoming_matches(target_date)
    print(f"  ✓ Found {len(matches)} matches")

    if not matches:
        print("\nNo matches found for the specified date.")
        return

    # Show team matching if requested
    if args.show_matching:
        print("\nTeam matching:")
        for match in matches:
            home_db = finder.find_team_in_db(match.home_team)
            away_db = finder.find_team_in_db(match.away_team)
            home_status = f"✓ {home_db}" if home_db else "✗ Not found"
            away_status = f"✓ {away_db}" if away_db else "✗ Not found"
            print(f"  {match.home_team}: {home_status}")
            print(f"  {match.away_team}: {away_status}")
            print()

    # Find value bets
    print(f"\nSearching for value bets (min edge: {args.min_edge:.0%})...")
    picks = finder.find_value_bets(matches)

    # Count by source
    ml_picks = [p for p in picks if p.get("source") == "ML Model"]
    other_picks = [p for p in picks if p.get("source") != "ML Model"]
    print(f"  ✓ Found {len(picks)} value bets ({len(ml_picks)} from ML model)")

    if args.json:
        print(json.dumps(picks, indent=2, default=str))
        return

    # Display results
    print()
    print("=" * 60)
    print("VALUE BETS (prioritert: Draw + BTTS fra ML-modell)")
    print("=" * 60)

    if not picks:
        print("\nIngen value bets funnet med gjeldende kriterier.")
        print("Prøv å senke --min-edge for flere resultater.")
    else:
        for i, pick in enumerate(picks, 1):
            conf_emoji = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(pick.get("confidence", ""), "⚪")
            source_tag = "[ML]" if pick.get("source") == "ML Model" else "[Heuristikk]"

            print(f"\n{conf_emoji} #{i}: {pick['home_team']} vs {pick['away_team']} {source_tag}")
            print(f"   Liga: {pick['league']}")
            print(f"   Tid: {pick['kickoff']}")

            # Handle different market types
            market = pick['market']
            if market == "Draw":
                odds = pick.get('odds_draw', 'N/A')
                odds_str = f"{odds:.2f}" if isinstance(odds, (int, float)) else odds
                print(f"   Pick: {market} @ {odds_str}")
            elif market == "BTTS":
                print(f"   Pick: {market} (ingen NT-odds)")
            else:
                odds_key = f"odds_{market.lower()}"
                odds = pick.get(odds_key, 'N/A')
                odds_str = f"{odds:.2f}" if isinstance(odds, (int, float)) else odds
                print(f"   Pick: {market} @ {odds_str}")

            # Show probability and edge
            model_prob = pick.get('model_prob') or pick.get('our_prob')
            if model_prob:
                print(f"   Modell: {model_prob:.1%}")

            edge = pick.get('edge')
            if edge is not None:
                print(f"   Edge: {edge:.1%}")

            print(f"   {pick['reasoning']}")

    # Save report if requested
    if args.report:
        report = finder.generate_report(picks, target_date)
        report_dir = Path(__file__).parent.parent / "data" / "predictions"
        report_dir.mkdir(parents=True, exist_ok=True)

        date_str = target_date.strftime("%Y-%m-%d") if target_date else datetime.now().strftime("%Y-%m-%d")
        report_path = report_dir / f"picks_{date_str}.md"

        with open(report_path, "w") as f:
            f.write(report)

        print(f"\n✓ Report saved to {report_path}")

    # Summary
    print()
    print("=" * 60)
    if picks:
        # Only count picks with edge for stake calculation
        picks_with_edge = [p for p in picks if p.get('edge') is not None]
        if picks_with_edge:
            total_stake = len(picks_with_edge) * 10
            avg_edge = sum(p['edge'] for p in picks_with_edge) / len(picks_with_edge)
            print(f"Draw-bets med edge: {len(picks_with_edge)} bets à 10 kr = {total_stake} kr")
            print(f"Gjennomsnittlig edge: {avg_edge:.1%}")

        btts_picks = [p for p in picks if p['market'] == 'BTTS']
        if btts_picks:
            print(f"BTTS-tips (uten NT-odds): {len(btts_picks)} kamper")
            print("  (Finn egne odds hos bookmaker for å beregne edge)")


if __name__ == "__main__":
    main()
