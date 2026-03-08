"""Bet Repository - manages placed bets in SQLite."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


DB_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "betbot.db"


class BetRepository:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.init_tables()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_tables(self):
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS placed_bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT,
                bet_type TEXT NOT NULL DEFAULT 'single',
                market TEXT,
                home_team TEXT,
                away_team TEXT,
                kickoff TEXT,
                league TEXT,
                odds REAL NOT NULL,
                amount REAL NOT NULL,
                model_prob REAL,
                edge REAL,
                consensus_count INTEGER,
                model_slug TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                payout REAL,
                profit REAL,
                settled_at TEXT,
                created_at TEXT NOT NULL
            )
        """)
        # Migration: add model_slug column if missing
        try:
            conn.execute("SELECT model_slug FROM placed_bets LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE placed_bets ADD COLUMN model_slug TEXT")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accumulator_legs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bet_id INTEGER NOT NULL REFERENCES placed_bets(id),
                match_id TEXT,
                market TEXT NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                kickoff TEXT,
                odds REAL,
                result TEXT NOT NULL DEFAULT 'pending'
            )
        """)
        conn.commit()
        conn.close()

    def place_bet(self, bet: dict) -> int:
        conn = self._conn()
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute("""
            INSERT INTO placed_bets
                (match_id, bet_type, market, home_team, away_team, kickoff, league,
                 odds, amount, model_prob, edge, consensus_count, model_slug, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (
            bet.get("match_id"),
            bet.get("bet_type", "single"),
            bet.get("market"),
            bet.get("home_team"),
            bet.get("away_team"),
            bet.get("kickoff"),
            bet.get("league"),
            bet["odds"],
            bet["amount"],
            bet.get("model_prob"),
            bet.get("edge"),
            bet.get("consensus_count"),
            bet.get("model_slug"),
            now,
        ))
        bet_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return bet_id

    def place_accumulator(self, bet: dict, legs: list[dict]) -> int:
        conn = self._conn()
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute("""
            INSERT INTO placed_bets
                (match_id, bet_type, market, home_team, away_team, kickoff, league,
                 odds, amount, model_prob, edge, consensus_count, model_slug, status, created_at)
            VALUES (?, 'accumulator', NULL, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (
            None,
            bet.get("kickoff"),
            bet.get("league"),
            bet["odds"],
            bet["amount"],
            bet.get("model_prob"),
            bet.get("edge"),
            bet.get("consensus_count"),
            bet.get("model_slug"),
            now,
        ))
        bet_id = cursor.lastrowid
        for leg in legs:
            conn.execute("""
                INSERT INTO accumulator_legs
                    (bet_id, match_id, market, home_team, away_team, kickoff, odds, result)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (
                bet_id,
                leg.get("match_id"),
                leg["market"],
                leg["home_team"],
                leg["away_team"],
                leg.get("kickoff"),
                leg.get("odds"),
            ))
        conn.commit()
        conn.close()
        return bet_id

    def get_bets(self, status: Optional[str] = None, limit: int = 50) -> list[dict]:
        conn = self._conn()
        if status:
            rows = conn.execute(
                "SELECT * FROM placed_bets WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM placed_bets ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

        bets = []
        for row in rows:
            bet = dict(row)
            if bet["bet_type"] == "accumulator":
                legs = conn.execute(
                    "SELECT * FROM accumulator_legs WHERE bet_id = ? ORDER BY id",
                    (bet["id"],),
                ).fetchall()
                bet["legs"] = [dict(l) for l in legs]
            else:
                bet["legs"] = None
            bets.append(bet)

        conn.close()
        return bets

    def get_summary(self) -> dict:
        conn = self._conn()
        active = conn.execute("""
            SELECT COUNT(*), COALESCE(SUM(amount), 0),
                   COALESCE(SUM(odds * amount), 0),
                   MAX(kickoff)
            FROM placed_bets WHERE status = 'pending'
        """).fetchone()
        settled = conn.execute("""
            SELECT
                COUNT(*),
                COALESCE(SUM(amount), 0),
                COALESCE(SUM(payout), 0),
                COALESCE(SUM(profit), 0),
                COALESCE(SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN status = 'lost' THEN 1 ELSE 0 END), 0)
            FROM placed_bets WHERE status IN ('won', 'lost')
        """).fetchone()
        conn.close()

        total_staked = settled[1]
        roi_pct = (settled[3] / total_staked * 100) if total_staked > 0 else 0.0

        return {
            "active_count": active[0],
            "active_amount": active[1],
            "max_potential_payout": round(active[2], 2),
            "latest_kickoff": active[3],
            "total_staked": total_staked,
            "total_payout": settled[2],
            "net_profit": settled[3],
            "roi_pct": round(roi_pct, 1),
            "win_count": settled[4],
            "loss_count": settled[5],
        }

    def get_placed_ids(self) -> list[dict]:
        conn = self._conn()
        # Single bets
        rows = conn.execute("""
            SELECT match_id, market, bet_type FROM placed_bets
            WHERE status != 'cancelled' AND bet_type = 'single' AND match_id IS NOT NULL
        """).fetchall()
        result = [dict(r) for r in rows]

        # Accumulator legs
        leg_rows = conn.execute("""
            SELECT al.match_id, al.market, 'accumulator' as bet_type
            FROM accumulator_legs al
            JOIN placed_bets pb ON al.bet_id = pb.id
            WHERE pb.status != 'cancelled'
        """).fetchall()
        result.extend(dict(r) for r in leg_rows)

        conn.close()
        return result

    def cancel_bet(self, bet_id: int) -> bool:
        conn = self._conn()
        cursor = conn.execute(
            "UPDATE placed_bets SET status = 'cancelled' WHERE id = ? AND status = 'pending'",
            (bet_id,),
        )
        conn.commit()
        ok = cursor.rowcount > 0
        conn.close()
        return ok

    def settle_bets(self) -> list[dict]:
        """Check pending bets against match results and settle them."""
        conn = self._conn()
        pending = conn.execute(
            "SELECT * FROM placed_bets WHERE status = 'pending'"
        ).fetchall()

        settled = []
        for bet in pending:
            bet = dict(bet)
            if bet["bet_type"] == "single":
                won = self._check_single_bet(conn, bet)
            else:
                won = self._check_accumulator(conn, bet)

            if won is None:
                continue  # match not played yet

            status = "won" if won else "lost"
            payout = bet["odds"] * bet["amount"] if won else 0.0
            profit = payout - bet["amount"]
            now = datetime.now(timezone.utc).isoformat()

            conn.execute("""
                UPDATE placed_bets
                SET status = ?, payout = ?, profit = ?, settled_at = ?
                WHERE id = ?
            """, (status, payout, profit, now, bet["id"]))

            bet.update(status=status, payout=payout, profit=profit)
            settled.append(bet)

        conn.commit()
        conn.close()
        return settled

    def _check_single_bet(self, conn: sqlite3.Connection, bet: dict) -> Optional[bool]:
        """Check if a single bet won. Returns None if match not played yet."""
        match_id = bet["match_id"]
        if not match_id:
            return None

        # Try to find the match by ID
        match = conn.execute(
            "SELECT result, total_goals, btts FROM matches WHERE id = ?",
            (match_id,)
        ).fetchone()

        if not match:
            # Try matching by team names and approximate date
            match = self._find_match_by_teams(conn, bet)

        if not match:
            return None

        match = dict(match)
        if match["result"] is None:
            return None

        return self._evaluate_market(bet["market"], match)

    def _find_match_by_teams(self, conn: sqlite3.Connection, bet: dict) -> Optional[dict]:
        """Try to find match by team names, filtered by kickoff date.

        Uses LIKE matching so that short names (e.g. 'Newcastle') match full
        names in the database (e.g. 'Newcastle United').
        """
        if not bet.get("home_team") or not bet.get("away_team"):
            return None
        home_pattern = f'{bet["home_team"]}%'
        away_pattern = f'{bet["away_team"]}%'
        kickoff = bet.get("kickoff")
        if kickoff:
            # Only match games within ±2 days of the bet's kickoff
            row = conn.execute("""
                SELECT result, total_goals, btts FROM matches
                WHERE home_team LIKE ? AND away_team LIKE ?
                  AND date(datetime(date_unix, 'unixepoch')) BETWEEN date(?, '-2 days') AND date(?, '+2 days')
                ORDER BY date_unix DESC LIMIT 1
            """, (home_pattern, away_pattern, kickoff, kickoff)).fetchone()
        else:
            row = conn.execute("""
                SELECT result, total_goals, btts FROM matches
                WHERE home_team LIKE ? AND away_team LIKE ?
                ORDER BY date_unix DESC LIMIT 1
            """, (home_pattern, away_pattern)).fetchone()
        return row

    def _check_accumulator(self, conn: sqlite3.Connection, bet: dict) -> Optional[bool]:
        """Check if all legs of an accumulator won. Returns None if any leg pending."""
        legs = conn.execute(
            "SELECT * FROM accumulator_legs WHERE bet_id = ?",
            (bet["id"],)
        ).fetchall()

        all_decided = True
        all_won = True

        for leg in legs:
            leg = dict(leg)
            if leg["result"] != "pending":
                if leg["result"] != "won":
                    all_won = False
                continue

            match = conn.execute(
                "SELECT result, total_goals, btts FROM matches WHERE id = ?",
                (leg.get("match_id"),)
            ).fetchone()

            if not match:
                match = self._find_match_by_teams(conn, leg)

            if not match or dict(match)["result"] is None:
                all_decided = False
                continue

            match = dict(match)
            won = self._evaluate_market(leg["market"], match)
            leg_result = "won" if won else "lost"
            conn.execute(
                "UPDATE accumulator_legs SET result = ? WHERE id = ?",
                (leg_result, leg["id"])
            )
            if not won:
                all_won = False

        if not all_decided:
            # If any leg already lost, we can settle as lost
            if not all_won:
                return False
            return None

        return all_won

    @staticmethod
    def _evaluate_market(market: str, match: dict) -> bool:
        m = market.lower().strip()
        result = match["result"]
        total_goals = match.get("total_goals") or 0
        btts = match.get("btts") or 0

        if m in ("home", "h", "hjemme", "hjemmeseier"):
            return result == "H"
        elif m in ("draw", "d", "uavgjort"):
            return result == "D"
        elif m in ("away", "a", "borte", "borteseier"):
            return result == "A"
        elif m in ("over 2.5", "over2.5", "o2.5"):
            return total_goals > 2.5
        elif m in ("under 2.5", "under2.5", "u2.5"):
            return total_goals < 2.5
        elif m in ("btts", "btts yes", "begge lag scorer"):
            return btts == 1
        elif m in ("btts no", "btts nei"):
            return btts == 0
        return False
