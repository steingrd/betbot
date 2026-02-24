"""
Daily Picks - Find value bets for upcoming matches.

Core logic extracted from scripts/daily_picks.py for reuse in TUI and CLI.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

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
    """Find daily value bet picks using ML model for Draw and BTTS."""

    def __init__(self, min_edge: float = 0.05, min_odds: float = 1.5, max_odds: float = 10.0):
        self.min_edge = min_edge
        self.min_odds = min_odds
        self.max_odds = max_odds

        # Deferred imports to avoid loading xgboost etc. at import time
        from src.analysis.value_finder import ValueBetFinder
        from src.data.data_processor import DataProcessor
        from src.data.norsk_tipping_client import NorskTippingClient

        self.nt_client = NorskTippingClient()
        self.processor = DataProcessor()
        self.predictor: Optional[MatchPredictor] = None
        self.engineer: Optional[FeatureEngineer] = None
        self.matches_df: Optional[pd.DataFrame] = None
        self.seasons_df: Optional[pd.DataFrame] = None
        self.value_finder = ValueBetFinder(min_edge, min_odds, max_odds)

    def load_model(self) -> bool:
        """Load the trained model and historical data."""
        try:
            from src.features.feature_engineering import FeatureEngineer
            from src.models.match_predictor import MatchPredictor

            self.predictor = MatchPredictor()
            self.predictor.load()

            self.matches_df = self.processor.load_matches()
            self.seasons_df = self.processor.load_seasons()
            self.engineer = FeatureEngineer(self.matches_df)
            return True
        except Exception as e:
            raise RuntimeError(f"Could not load model: {e}") from e

    def get_upcoming_matches(self, target_date: Optional[date] = None) -> list:
        """Get upcoming matches from Norsk Tipping."""
        if target_date:
            return self.nt_client.get_football_matches_for_date(target_date)
        return self.nt_client.get_upcoming_football_matches()

    def convert_nt_probs_to_odds(self, match) -> Dict[str, float]:
        """Convert Norsk Tipping probabilities to decimal odds."""
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
        """Normalize a team name for matching."""
        name_lower = name.lower().strip()
        if name_lower in TEAM_NAME_MAP:
            return TEAM_NAME_MAP[name_lower]
        return name

    def find_team_in_db(self, nt_name: str) -> Optional[str]:
        """Find a team in our database matching NT name."""
        if self.matches_df is None:
            return None

        normalized = self.normalize_team_name(nt_name)
        all_teams = set(self.matches_df["home_team"].unique()) | set(self.matches_df["away_team"].unique())

        if normalized in all_teams:
            return normalized

        name_lower = normalized.lower()
        for team in all_teams:
            if team.lower() == name_lower:
                return team

        for team in all_teams:
            team_lower = team.lower()
            if name_lower in team_lower or team_lower in name_lower:
                return team

        return None

    def compute_features_for_match(
        self, home_team: str, away_team: str, match_date: datetime
    ) -> Optional[pd.DataFrame]:
        """Compute features for an upcoming match using historical data."""
        if self.engineer is None or self.matches_df is None:
            return None

        date_unix = int(match_date.timestamp())
        historical = self.matches_df[self.matches_df["date_unix"] < date_unix].copy()

        if len(historical) == 0:
            return None

        home_matches = historical[
            (historical["home_team"] == home_team) | (historical["away_team"] == home_team)
        ].tail(10)

        away_matches = historical[
            (historical["home_team"] == away_team) | (historical["away_team"] == away_team)
        ].tail(10)

        if len(home_matches) < 3 or len(away_matches) < 3:
            return None

        home_form = self._compute_form(home_matches, home_team)
        away_form = self._compute_form(away_matches, away_team)

        recent_all = historical.tail(500)
        league_draw_rate = (recent_all["result"] == "D").mean() if len(recent_all) > 0 else 0.25

        features = {
            "match_id": f"upcoming_{home_team}_{away_team}",
            "home_team": home_team,
            "away_team": away_team,
            "game_week": 0,
            "date_unix": date_unix,
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
            "form_ppg_diff": home_form["ppg"] - away_form["ppg"],
            "position_diff": home_form.get("position", 10) - away_form.get("position", 10),
            "xg_diff": home_form.get("xg", 0) - away_form.get("xg", 0),
            "league_draw_rate": league_draw_rate,
            "h2h_home_wins": 0,
            "h2h_draws": 0,
            "h2h_away_wins": 0,
            "h2h_total_goals": 0,
            "home_prematch_ppg": home_form["ppg"],
            "away_prematch_ppg": away_form["ppg"],
            "home_overall_ppg": home_form["ppg"],
            "away_overall_ppg": away_form["ppg"],
            "prematch_ppg_diff": home_form["ppg"] - away_form["ppg"],
            "home_xg_prematch": home_form.get("xg", 1.3),
            "away_xg_prematch": away_form.get("xg", 1.0),
            "total_xg_prematch": home_form.get("xg", 1.3) + away_form.get("xg", 1.0),
            "xg_prematch_diff": home_form.get("xg", 1.3) - away_form.get("xg", 1.0),
            "home_attack_quality": 0.3,
            "away_attack_quality": 0.3,
            "fs_btts_potential": 50,
            "fs_o25_potential": 50,
            "fs_o35_potential": 30,
            "target_result": "D",
            "target_over_25": 0,
            "target_btts": 0,
        }

        return pd.DataFrame([features])

    def _compute_form(self, matches: pd.DataFrame, team: str) -> Dict:
        """Compute form statistics for a team."""
        if len(matches) == 0:
            return {
                "ppg": 1.0, "goals_for": 1.0, "goals_against": 1.0, "goal_diff": 0,
                "xg": 1.0, "venue_ppg": 1.0, "venue_goals_for": 1.0, "venue_goals_against": 1.0,
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

    def find_value_bets(self, matches: list) -> List[Dict]:
        """Find value bets using ML model for Draw and BTTS."""
        if not self.predictor or not self.predictor.is_fitted:
            return []

        picks = []

        for match in matches:
            home_db = self.find_team_in_db(match.home_team)
            away_db = self.find_team_in_db(match.away_team)

            match_info = {
                "home_team": match.home_team,
                "away_team": match.away_team,
                "home_team_db": home_db,
                "away_team_db": away_db,
                "league": match.league,
                "kickoff": match.kickoff.strftime("%H:%M") if match.kickoff else "--:--",
                "nt_home_prob": match.home_win_probability,
                "nt_draw_prob": match.draw_probability,
                "nt_away_prob": match.away_win_probability,
            }

            odds = self.convert_nt_probs_to_odds(match)
            match_info.update(odds)

            if home_db and away_db:
                features = self.compute_features_for_match(home_db, away_db, match.kickoff)

                if features is not None:
                    try:
                        predictions = self.predictor.predict(features)

                        model_draw = predictions["prob_D"].iloc[0]
                        model_btts = predictions["prob_btts"].iloc[0]

                        nt_draw_implied = match.draw_probability / 100 if match.draw_probability else 0

                        draw_edge = model_draw - nt_draw_implied
                        draw_odds = odds["odds_draw"]
                        if (
                            draw_edge >= self.min_edge
                            and draw_odds >= self.min_odds
                            and draw_odds <= self.max_odds
                        ):
                            confidence = "High" if draw_edge >= 0.10 else "Medium" if draw_edge >= 0.07 else "Low"
                            picks.append({
                                **match_info,
                                "market": "Draw",
                                "model_prob": model_draw,
                                "implied_prob": nt_draw_implied,
                                "edge": draw_edge,
                                "confidence": confidence,
                                "source": "ML Model",
                            })

                        if model_btts >= 0.55:
                            picks.append({
                                **match_info,
                                "market": "BTTS",
                                "model_prob": model_btts,
                                "implied_prob": None,
                                "edge": None,
                                "confidence": "High" if model_btts >= 0.65 else "Medium",
                                "source": "ML Model",
                            })

                    except Exception:
                        pass

        def sort_key(p):
            if p["edge"] is not None:
                return (0, -p["edge"])
            return (1, -p["model_prob"])

        picks.sort(key=sort_key)
        return picks
