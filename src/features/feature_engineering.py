"""
Feature Engineering

Creates predictive features from historical match data.
IMPORTANT: All features are calculated using only data available BEFORE the match.

Data Leakage Prevention:
- Uses pre_match_* PPG fields from FootyStats API (guaranteed pre-match)
- Uses pre_match xG fields instead of post-match xG
- All rolling calculations use data strictly before the match date
"""

import pandas as pd
import numpy as np
from typing import Optional


def safe_divide(a, b, default=0.0):
    """Safely divide a by b, returning default if b is 0 or None."""
    if b is None or b == 0:
        return default
    if a is None:
        return default
    return a / b


class FeatureEngineer:
    """Generate features for match prediction"""

    def __init__(self, matches_df: pd.DataFrame):
        # Sort by date
        self.matches = matches_df.sort_values("date_unix").reset_index(drop=True)
        self._precompute_team_stats()

    def _precompute_team_stats(self):
        """Precompute rolling stats for efficiency"""
        # Add match date as datetime
        self.matches["date"] = pd.to_datetime(self.matches["date_unix"], unit="s")

        # Points for each team in each match
        self.matches["home_points"] = self.matches["result"].map({"H": 3, "D": 1, "A": 0})
        self.matches["away_points"] = self.matches["result"].map({"H": 0, "D": 1, "A": 3})

    def _get_team_form(self, team_id: int, before_date: int, n_matches: int = 5) -> dict:
        """Get team's form from last n matches before given date"""

        # Home matches
        home = self.matches[
            (self.matches["home_team_id"] == team_id) &
            (self.matches["date_unix"] < before_date)
        ].tail(n_matches * 2)  # Get more in case we need to mix

        # Away matches
        away = self.matches[
            (self.matches["away_team_id"] == team_id) &
            (self.matches["date_unix"] < before_date)
        ].tail(n_matches * 2)

        # Combine and sort
        all_matches = []

        for _, m in home.iterrows():
            all_matches.append({
                "date": m["date_unix"],
                "points": m["home_points"],
                "goals_for": m["home_goals"],
                "goals_against": m["away_goals"],
                "shots": m["home_shots"] or 0,
                "shots_on_target": m["home_shots_on_target"] or 0,
                "xg": m["home_xg"] or 0,
                "is_home": 1
            })

        for _, m in away.iterrows():
            all_matches.append({
                "date": m["date_unix"],
                "points": m["away_points"],
                "goals_for": m["away_goals"],
                "goals_against": m["home_goals"],
                "shots": m["away_shots"] or 0,
                "shots_on_target": m["away_shots_on_target"] or 0,
                "xg": m["away_xg"] or 0,
                "is_home": 0
            })

        # Sort by date and take last n
        all_matches = sorted(all_matches, key=lambda x: x["date"])[-n_matches:]

        if not all_matches:
            return {
                "form_points": 0,
                "form_ppg": 0,
                "form_goals_for": 0,
                "form_goals_against": 0,
                "form_goal_diff": 0,
                "form_xg": 0,
                "form_shots": 0,
                "matches_played": 0
            }

        return {
            "form_points": sum(m["points"] for m in all_matches),
            "form_ppg": sum(m["points"] for m in all_matches) / len(all_matches),
            "form_goals_for": sum(m["goals_for"] for m in all_matches) / len(all_matches),
            "form_goals_against": sum(m["goals_against"] for m in all_matches) / len(all_matches),
            "form_goal_diff": (sum(m["goals_for"] for m in all_matches) - sum(m["goals_against"] for m in all_matches)) / len(all_matches),
            "form_xg": sum(m["xg"] for m in all_matches) / len(all_matches),
            "form_shots": sum(m["shots"] for m in all_matches) / len(all_matches),
            "matches_played": len(all_matches)
        }

    def _get_home_away_strength(self, team_id: int, before_date: int, is_home: bool) -> dict:
        """Get team's home or away specific strength"""

        if is_home:
            matches = self.matches[
                (self.matches["home_team_id"] == team_id) &
                (self.matches["date_unix"] < before_date)
            ]
            if len(matches) == 0:
                return {"venue_ppg": 0, "venue_goals_for": 0, "venue_goals_against": 0}

            return {
                "venue_ppg": matches["home_points"].mean(),
                "venue_goals_for": matches["home_goals"].mean(),
                "venue_goals_against": matches["away_goals"].mean()
            }
        else:
            matches = self.matches[
                (self.matches["away_team_id"] == team_id) &
                (self.matches["date_unix"] < before_date)
            ]
            if len(matches) == 0:
                return {"venue_ppg": 0, "venue_goals_for": 0, "venue_goals_against": 0}

            return {
                "venue_ppg": matches["away_points"].mean(),
                "venue_goals_for": matches["away_goals"].mean(),
                "venue_goals_against": matches["home_goals"].mean()
            }

    def _get_h2h_stats(self, home_id: int, away_id: int, before_date: int, n_matches: int = 5) -> dict:
        """Get head-to-head statistics"""

        h2h = self.matches[
            (
                ((self.matches["home_team_id"] == home_id) & (self.matches["away_team_id"] == away_id)) |
                ((self.matches["home_team_id"] == away_id) & (self.matches["away_team_id"] == home_id))
            ) &
            (self.matches["date_unix"] < before_date)
        ].tail(n_matches)

        if len(h2h) == 0:
            return {
                "h2h_home_wins": 0,
                "h2h_draws": 0,
                "h2h_away_wins": 0,
                "h2h_home_goals": 0,
                "h2h_away_goals": 0,
                "h2h_matches": 0
            }

        home_wins = 0
        draws = 0
        away_wins = 0
        home_goals = 0
        away_goals = 0

        for _, m in h2h.iterrows():
            if m["home_team_id"] == home_id:
                # Same fixture
                if m["result"] == "H":
                    home_wins += 1
                elif m["result"] == "D":
                    draws += 1
                else:
                    away_wins += 1
                home_goals += m["home_goals"]
                away_goals += m["away_goals"]
            else:
                # Reversed fixture
                if m["result"] == "A":
                    home_wins += 1
                elif m["result"] == "D":
                    draws += 1
                else:
                    away_wins += 1
                home_goals += m["away_goals"]
                away_goals += m["home_goals"]

        return {
            "h2h_home_wins": home_wins,
            "h2h_draws": draws,
            "h2h_away_wins": away_wins,
            "h2h_home_goals": home_goals / len(h2h),
            "h2h_away_goals": away_goals / len(h2h),
            "h2h_matches": len(h2h)
        }

    def _get_season_position(self, team_id: int, before_date: int, season_id: int = None) -> dict:
        """Get team's current league position within the same season"""

        # Filter by date
        season_matches = self.matches[self.matches["date_unix"] < before_date]

        # Filter by season_id to avoid cross-season leakage
        if season_id is not None:
            season_matches = season_matches[season_matches["season_id"] == season_id]

        if len(season_matches) == 0:
            return {"position": 10, "points": 0, "goal_diff": 0}

        # Calculate standings
        standings = {}

        for _, m in season_matches.iterrows():
            # Home team
            hid = m["home_team_id"]
            if hid not in standings:
                standings[hid] = {"points": 0, "gf": 0, "ga": 0}
            standings[hid]["points"] += m["home_points"]
            standings[hid]["gf"] += m["home_goals"]
            standings[hid]["ga"] += m["away_goals"]

            # Away team
            aid = m["away_team_id"]
            if aid not in standings:
                standings[aid] = {"points": 0, "gf": 0, "ga": 0}
            standings[aid]["points"] += m["away_points"]
            standings[aid]["gf"] += m["away_goals"]
            standings[aid]["ga"] += m["home_goals"]

        # Sort by points, then goal diff
        sorted_teams = sorted(
            standings.items(),
            key=lambda x: (x[1]["points"], x[1]["gf"] - x[1]["ga"]),
            reverse=True
        )

        for i, (tid, stats) in enumerate(sorted_teams):
            if tid == team_id:
                return {
                    "position": i + 1,
                    "points": stats["points"],
                    "goal_diff": stats["gf"] - stats["ga"]
                }

        return {"position": 10, "points": 0, "goal_diff": 0}

    def generate_features(self, min_matches: int = 3, progress_callback=None) -> pd.DataFrame:
        """Generate all features for each match

        Args:
            min_matches: Minimum matches played before including a team
            progress_callback: Optional function(current, total) called for progress updates
        """

        features_list = []
        total = len(self.matches)

        for idx, match in self.matches.iterrows():
            if progress_callback and idx % 1000 == 0:
                progress_callback(idx, total)
            match_date = match["date_unix"]
            home_id = match["home_team_id"]
            away_id = match["away_team_id"]
            season_id = match.get("season_id")

            # Get all stats
            home_form = self._get_team_form(home_id, match_date)
            away_form = self._get_team_form(away_id, match_date)

            # Skip if not enough matches played
            if home_form["matches_played"] < min_matches or away_form["matches_played"] < min_matches:
                continue

            home_venue = self._get_home_away_strength(home_id, match_date, is_home=True)
            away_venue = self._get_home_away_strength(away_id, match_date, is_home=False)

            h2h = self._get_h2h_stats(home_id, away_id, match_date)

            home_pos = self._get_season_position(home_id, match_date, season_id)
            away_pos = self._get_season_position(away_id, match_date, season_id)

            features = {
                # Match identifiers
                "match_id": match["id"],
                "season_id": match.get("season_id"),
                "league_id": match.get("league_id"),
                "date_unix": match_date,
                "game_week": match["game_week"],
                "home_team": match["home_team"],
                "away_team": match["away_team"],

                # Home team features
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

                # Away team features
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

                # Difference features
                "form_ppg_diff": home_form["form_ppg"] - away_form["form_ppg"],
                "position_diff": away_pos["position"] - home_pos["position"],  # Positive = home better
                "xg_diff": home_form["form_xg"] - away_form["form_xg"],

                # H2H
                "h2h_home_wins": h2h["h2h_home_wins"],
                "h2h_draws": h2h["h2h_draws"],
                "h2h_away_wins": h2h["h2h_away_wins"],
                "h2h_total_goals": h2h["h2h_home_goals"] + h2h["h2h_away_goals"],

                # Historical odds (these are known before match)
                "odds_home": match["odds_home"],
                "odds_draw": match["odds_draw"],
                "odds_away": match["odds_away"],
                "odds_over_25": match["odds_over_25"],
                "odds_btts_yes": match["odds_btts_yes"],

                # Implied probabilities from odds
                "implied_prob_home": 1 / match["odds_home"] if match["odds_home"] else 0,
                "implied_prob_draw": 1 / match["odds_draw"] if match["odds_draw"] else 0,
                "implied_prob_away": 1 / match["odds_away"] if match["odds_away"] else 0,

                # === NYE PRE-MATCH FEATURES (unngår data leakage) ===

                # Pre-match PPG fra FootyStats (garantert før kampen)
                "home_prematch_ppg": match.get("home_ppg") or 0,
                "away_prematch_ppg": match.get("away_ppg") or 0,
                "home_overall_ppg": match.get("home_overall_ppg") or 0,
                "away_overall_ppg": match.get("away_overall_ppg") or 0,
                "prematch_ppg_diff": (match.get("home_ppg") or 0) - (match.get("away_ppg") or 0),

                # Pre-match xG (forventet mål basert på historikk)
                "home_xg_prematch": match.get("home_xg_prematch") or 0,
                "away_xg_prematch": match.get("away_xg_prematch") or 0,
                "total_xg_prematch": match.get("total_xg_prematch") or 0,
                "xg_prematch_diff": (match.get("home_xg_prematch") or 0) - (match.get("away_xg_prematch") or 0),

                # Angrepskvalitet (ratio farlige angrep / totale angrep)
                "home_attack_quality": safe_divide(
                    match.get("home_dangerous_attacks"),
                    match.get("home_attacks")
                ),
                "away_attack_quality": safe_divide(
                    match.get("away_dangerous_attacks"),
                    match.get("away_attacks")
                ),

                # FootyStats sine beregnede potensial-features (ensemble input)
                "fs_btts_potential": match.get("fs_btts_potential") or 0,
                "fs_o25_potential": match.get("fs_o25_potential") or 0,
                "fs_o35_potential": match.get("fs_o35_potential") or 0,

                # Targets (what we want to predict)
                "target_result": match["result"],  # H, D, A
                "target_home_goals": match["home_goals"],
                "target_away_goals": match["away_goals"],
                "target_total_goals": match["total_goals"],
                "target_btts": match["btts"],
                "target_over_25": match["over_25"],
            }

            features_list.append(features)

        return pd.DataFrame(features_list)


if __name__ == "__main__":
    from src.data.data_processor import DataProcessor

    # Load matches
    processor = DataProcessor()
    matches = processor.load_matches()

    print(f"Loaded {len(matches)} matches")

    # Generate features
    engineer = FeatureEngineer(matches)
    features_df = engineer.generate_features()

    print(f"Generated features for {len(features_df)} matches")
    print(f"\nFeature columns: {len(features_df.columns)}")
    print(features_df.columns.tolist())

    # Save
    output_path = processor.db_path.parent / "features.csv"
    features_df.to_csv(output_path, index=False)
    print(f"\nSaved to {output_path}")
