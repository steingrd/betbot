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
    """Find daily value bet picks using multi-strategy consensus."""

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
        self.engineer: Optional[FeatureEngineer] = None
        self.matches_df: Optional[pd.DataFrame] = None
        self.matches_with_league: Optional[pd.DataFrame] = None
        self.seasons_df: Optional[pd.DataFrame] = None
        self.value_finder = ValueBetFinder(min_edge, min_odds, max_odds)
        self._strategies: list = []

    def load_model(self) -> bool:
        """Load all trained strategy models and historical data."""
        try:
            from pathlib import Path

            from src.features.feature_engineering import FeatureEngineer
            from src.strategies import STRATEGIES

            self.matches_df = self.processor.load_matches()
            self.matches_with_league = self.processor.load_matches_with_league()
            self.seasons_df = self.processor.load_seasons()
            self.engineer = FeatureEngineer(self.matches_df)

            # Load all strategies
            models_dir = Path(__file__).parent.parent.parent / "models"
            self._strategies = []
            for strategy in STRATEGIES:
                ext = "json" if strategy.slug in ("poisson", "elo") else "pkl"
                model_path = models_dir / f"{strategy.slug}.{ext}"
                if strategy.load(model_path):
                    self._strategies.append(strategy)
                    logger.info("Loaded strategy: %s", strategy.name)

            logger.info("Loaded %d/%d strategies", len(self._strategies), len(STRATEGIES))
            return len(self._strategies) > 0
        except Exception as e:
            raise RuntimeError(f"Could not load models: {e}") from e

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

    def _run_strategies_on_matches(self, matches: list) -> List[Dict]:
        """Run all strategies on NT matches. Returns raw data per match.

        Each entry contains: home_team, away_team, home_db, away_db, league,
        kickoff, odds, features, strategy_predictions, strategy_names.
        """
        if not self._strategies:
            return []

        match_data = []

        for match in matches:
            home_db = self.find_team_in_db(match.home_team)
            away_db = self.find_team_in_db(match.away_team)

            if not home_db or not away_db:
                continue

            features = self.compute_features_for_match(home_db, away_db, match.kickoff)
            if features is None:
                continue

            odds = self.convert_nt_probs_to_odds(match)
            kickoff_str = match.kickoff.strftime("%Y-%m-%d %H:%M") if match.kickoff else "--:--"

            # Build a fake matches_df for strategies that need it
            match_df = pd.DataFrame([{
                "match_id": features["match_id"].iloc[0],
                "home_team": home_db,
                "away_team": away_db,
                "league_name": match.league or "",
            }])

            # Run each strategy
            strategy_predictions = {}
            strategy_names = {}
            for strategy in self._strategies:
                try:
                    preds = strategy.predict(match_df, features)
                    strategy_predictions[strategy.slug] = preds
                    strategy_names[strategy.slug] = strategy.name
                except Exception as e:
                    logger.warning(
                        "%s prediction failed for %s vs %s: %s",
                        strategy.name, home_db, away_db, e
                    )

            if not strategy_predictions:
                continue

            match_data.append({
                "home_team": match.home_team,
                "away_team": match.away_team,
                "home_db": home_db,
                "away_db": away_db,
                "league": match.league,
                "kickoff": kickoff_str,
                "odds": odds,
                "features": features,
                "strategy_predictions": strategy_predictions,
                "strategy_names": strategy_names,
            })

        return match_data

    def find_value_bets(self, match_data: List[Dict]) -> List[Dict]:
        """Find value bets using multi-strategy consensus.

        Args:
            match_data: Output from _run_strategies_on_matches().

        Returns consensus bets with per-strategy signal info so the UI
        can filter by threshold.
        """
        from src.strategies.consensus import ConsensusEngine

        picks = []

        for md in match_data:
            odds = md["odds"]
            features = md["features"]

            # Build odds DataFrame for ConsensusEngine
            odds_row = {
                "match_id": features["match_id"].iloc[0],
                "home_team": md["home_team"],
                "away_team": md["away_team"],
                "league_name": md["league"] or "",
                "kickoff": md["kickoff"],
                "odds_home": odds["odds_home"],
                "odds_draw": odds["odds_draw"],
                "odds_away": odds["odds_away"],
                "odds_over_25": 0,  # NT doesn't provide these
                "odds_btts_yes": 0,
            }
            odds_df = pd.DataFrame([odds_row])

            # Find consensus bets
            engine = ConsensusEngine()
            consensus_bets = engine.find_consensus_bets(
                md["strategy_predictions"], md["strategy_names"], odds_df, min_edge=self.min_edge
            )

            for bet in consensus_bets:
                # Skip markets without proper odds from NT
                if bet.market in ("Over 2.5", "BTTS") and bet.odds <= 0:
                    continue

                avg_prob = sum(s.model_prob for s in bet.signals if s.is_value) / max(
                    sum(1 for s in bet.signals if s.is_value), 1
                )
                avg_edge = avg_prob - bet.implied_prob

                confidence = "High" if bet.consensus_count >= 3 else "Medium" if bet.consensus_count >= 2 else "Low"

                picks.append({
                    "home_team": md["home_team"],
                    "away_team": md["away_team"],
                    "home_team_db": md["home_db"],
                    "away_team_db": md["away_db"],
                    "league": md["league"],
                    "kickoff": md["kickoff"],
                    "market": bet.market,
                    "model_prob": round(avg_prob, 4),
                    "implied_prob": bet.implied_prob,
                    "edge": round(avg_edge, 4),
                    "confidence": confidence,
                    "odds_home": odds["odds_home"],
                    "odds_draw": odds["odds_draw"],
                    "odds_away": odds["odds_away"],
                    "consensus_count": bet.consensus_count,
                    "total_strategies": bet.total_strategies,
                    "signals": [
                        {
                            "strategy": s.strategy_name,
                            "prob": round(s.model_prob, 4),
                            "edge": round(s.edge, 4),
                            "is_value": s.is_value,
                        }
                        for s in bet.signals
                    ],
                })

        picks.sort(key=lambda p: (-p["consensus_count"], -(p["edge"] or 0)))
        return picks

    def find_safe_picks(self, match_data: List[Dict], min_prob: float = 0.60) -> List[Dict]:
        """Find the most probable 1X2 outcomes regardless of value/edge.

        Useful for accumulator bets where you want high-confidence picks.

        Args:
            match_data: Output from _run_strategies_on_matches().
            min_prob: Minimum average probability across strategies.

        Returns list sorted by descending avg_prob.
        """
        import math

        picks = []

        for md in match_data:
            odds = md["odds"]

            # Collect 1X2 probabilities from all strategies
            outcomes = {}  # outcome -> list of probs
            for slug, preds_df in md["strategy_predictions"].items():
                if preds_df.empty:
                    continue
                row = preds_df.iloc[0]
                for outcome, col in [("H", "prob_H"), ("D", "prob_D"), ("A", "prob_A")]:
                    prob = float(row.get(col, float("nan")))
                    if not math.isnan(prob):
                        outcomes.setdefault(outcome, []).append((slug, prob))

            if not outcomes:
                continue

            # Find best outcome by average probability
            best_outcome = None
            best_avg = 0.0
            best_probs = []

            for outcome, strat_probs in outcomes.items():
                avg = sum(p for _, p in strat_probs) / len(strat_probs)
                if avg > best_avg:
                    best_avg = avg
                    best_outcome = outcome
                    best_probs = strat_probs

            if best_outcome is None or best_avg < min_prob:
                continue

            # Map outcome to label and odds
            outcome_map = {"H": ("Hjemmeseier", odds["odds_home"]),
                           "D": ("Uavgjort", odds["odds_draw"]),
                           "A": ("Borteseier", odds["odds_away"])}
            label, outcome_odds = outcome_map[best_outcome]

            picks.append({
                "home_team": md["home_team"],
                "away_team": md["away_team"],
                "league": md["league"],
                "kickoff": md["kickoff"],
                "predicted_outcome": label,
                "avg_prob": round(best_avg, 4),
                "consensus_count": len(best_probs),
                "total_strategies": len(md["strategy_predictions"]),
                "odds": round(outcome_odds, 2) if outcome_odds else None,
                "strategy_probs": {slug: round(p, 4) for slug, p in best_probs},
            })

        picks.sort(key=lambda p: -p["avg_prob"])
        return picks

    def generate_accumulators(self, safe_picks: List[Dict], sizes: List[int] | None = None) -> List[Dict]:
        """Generate accumulator combinations from safe picks.

        Takes the top N picks for each size and computes combined odds.

        Args:
            safe_picks: Output from find_safe_picks(), sorted by avg_prob desc.
            sizes: List of accumulator sizes to generate. Default [4, 6, 8].

        Returns list of accumulators with combined odds.
        """
        if sizes is None:
            sizes = [4, 6, 8]

        if not safe_picks:
            return []

        accumulators = []
        for size in sizes:
            if len(safe_picks) < size:
                continue

            top_picks = safe_picks[:size]

            # Only include if all picks have valid odds
            if not all(p.get("odds") and p["odds"] > 0 for p in top_picks):
                continue

            combined_odds = 1.0
            for p in top_picks:
                combined_odds *= p["odds"]

            probs = [p["avg_prob"] for p in top_picks]

            accumulators.append({
                "size": size,
                "combined_odds": round(combined_odds, 2),
                "min_prob": round(min(probs), 4),
                "avg_prob": round(sum(probs) / len(probs), 4),
                "picks": top_picks,
            })

        return accumulators

    def find_confident_goals(self, match_data: List[Dict], min_prob: float = 0.55) -> List[Dict]:
        """Find matches where the model is confident about BTTS or Over 2.5.

        Uses XGBoost, Poisson, and LogReg (not Elo, which only supports 1X2).
        NT doesn't provide odds for these markets, so we only show probability.

        Args:
            match_data: Output from _run_strategies_on_matches().
            min_prob: Minimum average probability across strategies.

        Returns list sorted by descending avg_prob.
        """
        import math

        picks = []

        for md in match_data:
            for market, prob_col in [("Over 2.5", "prob_over25"), ("BTTS", "prob_btts")]:
                strat_probs = []

                for slug, preds_df in md["strategy_predictions"].items():
                    # Skip Elo — only supports 1X2
                    if slug == "elo":
                        continue
                    if preds_df.empty:
                        continue
                    row = preds_df.iloc[0]
                    prob = float(row.get(prob_col, float("nan")))
                    if not math.isnan(prob):
                        strat_probs.append((slug, prob))

                if not strat_probs:
                    continue

                avg_prob = sum(p for _, p in strat_probs) / len(strat_probs)
                consensus = sum(1 for _, p in strat_probs if p >= min_prob)

                if avg_prob < min_prob:
                    continue

                picks.append({
                    "home_team": md["home_team"],
                    "away_team": md["away_team"],
                    "league": md["league"],
                    "kickoff": md["kickoff"],
                    "market": market,
                    "avg_prob": round(avg_prob, 4),
                    "consensus_count": consensus,
                    "total_strategies": len(strat_probs),
                    "strategy_probs": {slug: round(p, 4) for slug, p in strat_probs},
                })

        picks.sort(key=lambda p: -p["avg_prob"])
        return picks
