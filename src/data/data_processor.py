"""
Data Processor

Converts raw API data to structured DataFrames and stores in SQLite.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional
import pandas as pd

from .footystats_client import FootyStatsClient


class DataProcessor:
    """Process and store football match data"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path(__file__).parent.parent.parent / "data" / "processed" / "betbot.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def init_database(self):
        """Create database tables"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Matches table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY,
                season_id INTEGER,
                league_id INTEGER,
                season TEXT,
                game_week INTEGER,
                date_unix INTEGER,

                -- Teams
                home_team_id INTEGER,
                home_team TEXT,
                away_team_id INTEGER,
                away_team TEXT,

                -- Result
                home_goals INTEGER,
                away_goals INTEGER,
                total_goals INTEGER,
                result TEXT,  -- H, D, A

                -- Stats
                home_shots INTEGER,
                away_shots INTEGER,
                home_shots_on_target INTEGER,
                away_shots_on_target INTEGER,
                home_possession INTEGER,
                away_possession INTEGER,
                home_corners INTEGER,
                away_corners INTEGER,
                home_fouls INTEGER,
                away_fouls INTEGER,
                home_yellow_cards INTEGER,
                away_yellow_cards INTEGER,
                home_red_cards INTEGER,
                away_red_cards INTEGER,

                -- xG
                home_xg REAL,
                away_xg REAL,

                -- Halftime
                home_ht_goals INTEGER,
                away_ht_goals INTEGER,

                -- Odds (1X2)
                odds_home REAL,
                odds_draw REAL,
                odds_away REAL,

                -- Odds (Over/Under)
                odds_over_25 REAL,
                odds_under_25 REAL,
                odds_over_15 REAL,
                odds_under_15 REAL,

                -- Odds (BTTS)
                odds_btts_yes REAL,
                odds_btts_no REAL,

                -- Calculated
                btts INTEGER,  -- 0 or 1
                over_25 INTEGER,  -- 0 or 1
                over_15 INTEGER,

                -- Pre-match PPG (garantert før kampen)
                home_ppg REAL,
                away_ppg REAL,
                home_overall_ppg REAL,
                away_overall_ppg REAL,

                -- Pre-match xG
                home_xg_prematch REAL,
                away_xg_prematch REAL,
                total_xg_prematch REAL,

                -- Angrepsstatistikk
                home_attacks INTEGER,
                away_attacks INTEGER,
                home_dangerous_attacks INTEGER,
                away_dangerous_attacks INTEGER,

                -- FootyStats potensial/sannsynligheter
                fs_btts_potential REAL,
                fs_o25_potential REAL,
                fs_o35_potential REAL,
                fs_corners_potential REAL,

                -- Ekstra odds
                odds_over_35 REAL,
                odds_over_45 REAL,

                UNIQUE(id)
            )
        """)

        # Teams table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY,
                name TEXT,
                country TEXT,
                UNIQUE(id)
            )
        """)

        # Seasons table (with league metadata for proper holdout splits)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS seasons (
                id INTEGER PRIMARY KEY,
                league_id INTEGER,
                league_name TEXT,
                country TEXT,
                year TEXT,
                season_label TEXT,
                start_date INTEGER,
                end_date INTEGER,
                UNIQUE(id)
            )
        """)

        # Migrate existing seasons table if missing columns
        cursor.execute("PRAGMA table_info(seasons)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        new_cols = [
            ("league_id", "INTEGER"),
            ("league_name", "TEXT"),
            ("season_label", "TEXT"),
            ("start_date", "INTEGER"),
            ("end_date", "INTEGER"),
        ]
        for col_name, col_type in new_cols:
            if col_name not in existing_cols:
                cursor.execute(f"ALTER TABLE seasons ADD COLUMN {col_name} {col_type}")

        # Migrate existing matches table if missing league_id
        cursor.execute("PRAGMA table_info(matches)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        if "league_id" not in existing_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN league_id INTEGER")

        conn.commit()
        conn.close()

    def process_matches(self, matches_data: list, season_id: int, league_id: int = None) -> pd.DataFrame:
        """Convert raw match data to DataFrame

        Args:
            matches_data: Raw match data from API
            season_id: Season ID from FootyStats
            league_id: League ID from FootyStats (optional, for grouping)
        """

        records = []
        for m in matches_data:
            # Determine result
            home_goals = m.get("homeGoalCount", 0)
            away_goals = m.get("awayGoalCount", 0)
            if home_goals > away_goals:
                result = "H"
            elif away_goals > home_goals:
                result = "A"
            else:
                result = "D"

            record = {
                "id": m.get("id"),
                "season_id": season_id,
                "league_id": league_id,
                "season": m.get("season"),
                "game_week": m.get("game_week"),
                "date_unix": m.get("date_unix"),

                # Teams
                "home_team_id": m.get("homeID"),
                "home_team": m.get("home_name"),
                "away_team_id": m.get("awayID"),
                "away_team": m.get("away_name"),

                # Result
                "home_goals": home_goals,
                "away_goals": away_goals,
                "total_goals": m.get("totalGoalCount", 0),
                "result": result,

                # Stats
                "home_shots": m.get("team_a_shots"),
                "away_shots": m.get("team_b_shots"),
                "home_shots_on_target": m.get("team_a_shotsOnTarget"),
                "away_shots_on_target": m.get("team_b_shotsOnTarget"),
                "home_possession": m.get("team_a_possession"),
                "away_possession": m.get("team_b_possession"),
                "home_corners": m.get("team_a_corners"),
                "away_corners": m.get("team_b_corners"),
                "home_fouls": m.get("team_a_fouls"),
                "away_fouls": m.get("team_b_fouls"),
                "home_yellow_cards": m.get("team_a_yellow_cards"),
                "away_yellow_cards": m.get("team_b_yellow_cards"),
                "home_red_cards": m.get("team_a_red_cards"),
                "away_red_cards": m.get("team_b_red_cards"),

                # xG
                "home_xg": m.get("team_a_xg"),
                "away_xg": m.get("team_b_xg"),

                # Halftime
                "home_ht_goals": m.get("ht_goals_team_a"),
                "away_ht_goals": m.get("ht_goals_team_b"),

                # Odds
                "odds_home": m.get("odds_ft_1"),
                "odds_draw": m.get("odds_ft_x"),
                "odds_away": m.get("odds_ft_2"),
                "odds_over_25": m.get("odds_ft_over25"),
                "odds_under_25": m.get("odds_ft_under25"),
                "odds_over_15": m.get("odds_ft_over15"),
                "odds_under_15": m.get("odds_ft_under15"),
                "odds_btts_yes": m.get("odds_btts_yes"),
                "odds_btts_no": m.get("odds_btts_no"),

                # Calculated
                "btts": 1 if m.get("btts") else 0,
                "over_25": 1 if m.get("over25") else 0,
                "over_15": 1 if m.get("over15") else 0,

                # Pre-match PPG (bruker pre_match_* felter for å unngå data leakage)
                "home_ppg": m.get("pre_match_home_ppg"),
                "away_ppg": m.get("pre_match_away_ppg"),
                "home_overall_ppg": m.get("pre_match_teamA_overall_ppg"),
                "away_overall_ppg": m.get("pre_match_teamB_overall_ppg"),

                # Pre-match xG
                "home_xg_prematch": m.get("team_a_xg_prematch"),
                "away_xg_prematch": m.get("team_b_xg_prematch"),
                "total_xg_prematch": m.get("total_xg_prematch"),

                # Angrepsstatistikk
                "home_attacks": m.get("team_a_attacks"),
                "away_attacks": m.get("team_b_attacks"),
                "home_dangerous_attacks": m.get("team_a_dangerous_attacks"),
                "away_dangerous_attacks": m.get("team_b_dangerous_attacks"),

                # FootyStats potensial/sannsynligheter
                "fs_btts_potential": m.get("btts_potential"),
                "fs_o25_potential": m.get("o25_potential"),
                "fs_o35_potential": m.get("o35_potential"),
                "fs_corners_potential": m.get("corners_potential"),

                # Ekstra odds
                "odds_over_35": m.get("odds_ft_over35"),
                "odds_over_45": m.get("odds_ft_over45"),
            }
            records.append(record)

        return pd.DataFrame(records)

    def save_matches(self, df: pd.DataFrame):
        """Save matches DataFrame to database using upsert (INSERT OR REPLACE)."""
        if df.empty:
            return
        conn = self._get_connection()
        columns = list(df.columns)
        placeholders = ", ".join(["?"] * len(columns))
        col_names = ", ".join(columns)
        sql = f"INSERT OR REPLACE INTO matches ({col_names}) VALUES ({placeholders})"
        # Convert NaN to None for proper SQL NULL handling
        records = [
            tuple(None if pd.isna(v) else v for v in row)
            for row in df.itertuples(index=False, name=None)
        ]
        conn.executemany(sql, records)
        conn.commit()
        conn.close()

    def load_matches(self, season_id: Optional[int] = None) -> pd.DataFrame:
        """Load matches from database"""
        conn = self._get_connection()
        if season_id:
            df = pd.read_sql_query(
                "SELECT * FROM matches WHERE season_id = ?",
                conn,
                params=[season_id]
            )
        else:
            df = pd.read_sql_query("SELECT * FROM matches", conn)
        conn.close()
        return df

    def get_all_teams(self) -> pd.DataFrame:
        """Get unique teams from matches"""
        conn = self._get_connection()
        df = pd.read_sql_query("""
            SELECT DISTINCT home_team_id as id, home_team as name
            FROM matches
            UNION
            SELECT DISTINCT away_team_id as id, away_team as name
            FROM matches
        """, conn)
        conn.close()
        return df

    def save_season(self, season_id: int, league_id: int, league_name: str,
                    country: str, year, season_label: str = None):
        """Save season metadata to database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        # Ensure proper types
        season_id = int(season_id) if season_id is not None else None
        league_id = int(league_id) if league_id is not None else None
        year_str = str(year) if year is not None else None
        cursor.execute("""
            INSERT OR REPLACE INTO seasons
            (id, league_id, league_name, country, year, season_label)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (season_id, league_id, league_name, country, year_str, season_label))
        conn.commit()
        conn.close()

    def update_season_dates(self, season_id: int, start_date: int, end_date: int):
        """Update season start/end dates from match data"""
        conn = self._get_connection()
        cursor = conn.cursor()
        # Ensure int conversion for pandas int64 compatibility
        cursor.execute("""
            UPDATE seasons SET start_date = ?, end_date = ?
            WHERE id = ?
        """, (int(start_date), int(end_date), int(season_id)))
        conn.commit()
        conn.close()

    def load_seasons(self) -> pd.DataFrame:
        """Load all seasons with metadata"""
        conn = self._get_connection()
        df = pd.read_sql_query("SELECT * FROM seasons", conn)
        conn.close()
        return df

    def load_matches_with_league(self) -> pd.DataFrame:
        """Load matches joined with season/league info"""
        conn = self._get_connection()
        df = pd.read_sql_query("""
            SELECT m.*, s.league_id as s_league_id, s.league_name, s.country,
                   s.start_date as season_start, s.end_date as season_end
            FROM matches m
            LEFT JOIN seasons s ON m.season_id = s.id
        """, conn)
        # Use season's league_id if match doesn't have it
        if "s_league_id" in df.columns:
            df["league_id"] = df["league_id"].fillna(df["s_league_id"])
            df = df.drop(columns=["s_league_id"])
        conn.close()
        return df

    def get_seasons_by_league(self) -> pd.DataFrame:
        """Get seasons grouped by league with date ranges"""
        conn = self._get_connection()
        df = pd.read_sql_query("""
            SELECT s.id as season_id, s.league_id, s.league_name, s.country,
                   s.year, s.season_label, s.start_date, s.end_date,
                   COUNT(m.id) as match_count
            FROM seasons s
            LEFT JOIN matches m ON s.id = m.season_id
            GROUP BY s.id
            ORDER BY s.league_id, s.start_date
        """, conn)
        conn.close()
        return df


def download_and_process(api_key: str = "example", season_id: int = 1625):
    """Download and process data for a season"""

    print(f"Downloading season {season_id}...")
    client = FootyStatsClient(api_key=api_key)
    processor = DataProcessor()

    # Initialize database
    processor.init_database()

    # Get matches
    response = client.get_league_matches(season_id)
    matches = response.get("data", []) if isinstance(response, dict) else response

    print(f"Processing {len(matches)} matches...")
    df = processor.process_matches(matches, season_id)

    # Save to database
    processor.save_matches(df)
    print(f"Saved to {processor.db_path}")

    # Also save to CSV for easy inspection
    csv_path = processor.db_path.parent / f"matches_{season_id}.csv"
    df.to_csv(csv_path, index=False)
    print(f"Also saved to {csv_path}")

    return df


if __name__ == "__main__":
    df = download_and_process()
    print(f"\nDataset shape: {df.shape}")
    print(f"\nResult distribution:\n{df['result'].value_counts()}")
    print(f"\nGoals per game: {df['total_goals'].mean():.2f}")
