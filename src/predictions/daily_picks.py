"""
Daily Picks - Find value bets for upcoming matches.

Core logic extracted from scripts/daily_picks.py for reuse in TUI and CLI.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

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
            if prob is None or prob <= 0:
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
        """Compute features for an upcoming match using the same feature engine as training."""
        if self.engineer is None or self.matches_df is None:
            return None

        date_unix = int(match_date.timestamp())

        # Use engineer's pre-sorted matches (sorted by date_unix in FeatureEngineer.__init__)
        hist = self.engineer.matches[self.engineer.matches["date_unix"] < date_unix]

        if len(hist) == 0:
            return None

        # Look up team IDs from historical data (most recent occurrence)
        home_as_home = hist[hist["home_team"] == home_team]
        home_as_away = hist[hist["away_team"] == home_team]
        away_as_home = hist[hist["home_team"] == away_team]
        away_as_away = hist[hist["away_team"] == away_team]

        home_all = pd.concat([home_as_home, home_as_away])
        away_all = pd.concat([away_as_home, away_as_away])

        if len(home_all) < 3 or len(away_all) < 3:
            return None

        last_home = home_all.sort_values("date_unix").iloc[-1]
        home_id = last_home["home_team_id"] if last_home["home_team"] == home_team else last_home["away_team_id"]

        last_away = away_all.sort_values("date_unix").iloc[-1]
        away_id = last_away["away_team_id"] if last_away["away_team"] == away_team else last_away["home_team_id"]

        # Infer season_id and league_id from the most recent match for home team
        season_id = last_home.get("season_id")
        league_id = last_home.get("league_id")
        if pd.isna(season_id):
            season_id = None
        if pd.isna(league_id):
            league_id = None

        # Use same FeatureEngineer methods as training
        home_form = self.engineer._get_team_form(home_id, date_unix)
        away_form = self.engineer._get_team_form(away_id, date_unix)

        if home_form["matches_played"] < 3 or away_form["matches_played"] < 3:
            return None

        home_venue = self.engineer._get_home_away_strength(home_id, date_unix, is_home=True)
        away_venue = self.engineer._get_home_away_strength(away_id, date_unix, is_home=False)
        h2h = self.engineer._get_h2h_stats(home_id, away_id, date_unix)
        home_pos = self.engineer._get_season_position(home_id, date_unix, season_id)
        away_pos = self.engineer._get_season_position(away_id, date_unix, season_id)
        league_draw_rate = self.engineer._get_league_draw_rate(league_id, date_unix)

        features = {
            "match_id": f"upcoming_{home_team}_{away_team}",
            "home_team": home_team,
            "away_team": away_team,
            "game_week": 0,
            "date_unix": date_unix,
            "home_form_ppg": home_form["form_ppg"],
            "home_form_goals_for": home_form["form_goals_for"],
            "home_form_goals_against": home_form["form_goals_against"],
            "home_form_goal_diff": home_form["form_goal_diff"],
            "home_form_xg": home_form["form_xg"],
            "home_venue_ppg": home_venue["venue_ppg"],
            "home_venue_goals_for": home_venue["venue_goals_for"],
            "home_venue_goals_against": home_venue["venue_goals_against"],
            "home_position": home_pos["position"],
            "home_season_points": home_pos["points"],
            "home_season_gd": home_pos["goal_diff"],
            "away_form_ppg": away_form["form_ppg"],
            "away_form_goals_for": away_form["form_goals_for"],
            "away_form_goals_against": away_form["form_goals_against"],
            "away_form_goal_diff": away_form["form_goal_diff"],
            "away_form_xg": away_form["form_xg"],
            "away_venue_ppg": away_venue["venue_ppg"],
            "away_venue_goals_for": away_venue["venue_goals_for"],
            "away_venue_goals_against": away_venue["venue_goals_against"],
            "away_position": away_pos["position"],
            "away_season_points": away_pos["points"],
            "away_season_gd": away_pos["goal_diff"],
            "form_ppg_diff": home_form["form_ppg"] - away_form["form_ppg"],
            # Consistent with training: away_pos - home_pos (positive = home better, lower number = higher rank)
            "position_diff": away_pos["position"] - home_pos["position"],
            "xg_diff": home_form["form_xg"] - away_form["form_xg"],
            "league_draw_rate": league_draw_rate,
            "h2h_home_wins": h2h["h2h_home_wins"],
            "h2h_draws": h2h["h2h_draws"],
            "h2h_away_wins": h2h["h2h_away_wins"],
            "h2h_total_goals": h2h["h2h_home_goals"] + h2h["h2h_away_goals"],
            "home_prematch_ppg": home_form["form_ppg"],
            "away_prematch_ppg": away_form["form_ppg"],
            "home_overall_ppg": home_form["form_ppg"],
            "away_overall_ppg": away_form["form_ppg"],
            "prematch_ppg_diff": home_form["form_ppg"] - away_form["form_ppg"],
            "home_xg_prematch": home_form["form_xg"],
            "away_xg_prematch": away_form["form_xg"],
            "total_xg_prematch": home_form["form_xg"] + away_form["form_xg"],
            "xg_prematch_diff": home_form["form_xg"] - away_form["form_xg"],
            # Pre-match attack stats are not available for upcoming matches
            "home_attack_quality": 0.0,
            "away_attack_quality": 0.0,
            "fs_btts_potential": 0,
            "fs_o25_potential": 0,
            "fs_o35_potential": 0,
            "target_result": "D",
            "target_over_25": 0,
            "target_btts": 0,
        }

        return pd.DataFrame([features])

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

                    except Exception as e:
                        logger.warning(
                            "Prediction failed for %s vs %s: %s",
                            home_db, away_db, e, exc_info=True
                        )

        def sort_key(p):
            if p["edge"] is not None:
                return (0, -p["edge"])
            return (1, -p["model_prob"])

        picks.sort(key=sort_key)
        return picks
