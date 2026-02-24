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
    python scripts/daily_picks.py --json             # Output as JSON
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.predictions.daily_picks import DailyPicksFinder


def main():
    parser = argparse.ArgumentParser(description="Find daily value bet picks")
    parser.add_argument("--date", type=str, help="Target date (YYYY-MM-DD)")
    parser.add_argument("--min-edge", type=float, default=0.05, help="Minimum edge (default: 0.05)")
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

    # Try to load model
    print("Loading model and historical data...")
    try:
        finder.load_model()
        print("  Model loaded")
        print(f"  {len(finder.matches_df)} historical matches loaded")
    except RuntimeError as e:
        print(f"  Model not available: {e}")

    # Get upcoming matches
    print("\nFetching upcoming matches from Norsk Tipping...")
    matches = finder.get_upcoming_matches(target_date)
    print(f"  Found {len(matches)} matches")

    if not matches:
        print("\nNo matches found for the specified date.")
        return

    # Show team matching if requested
    if args.show_matching:
        print("\nTeam matching:")
        for match in matches:
            home_db = finder.find_team_in_db(match.home_team)
            away_db = finder.find_team_in_db(match.away_team)
            home_status = f"  {home_db}" if home_db else "  Not found"
            away_status = f"  {away_db}" if away_db else "  Not found"
            print(f"  {match.home_team}: {home_status}")
            print(f"  {match.away_team}: {away_status}")
            print()

    # Find value bets
    print(f"\nSearching for value bets (min edge: {args.min_edge:.0%})...")
    picks = finder.find_value_bets(matches)

    ml_picks = [p for p in picks if p.get("source") == "ML Model"]
    print(f"  Found {len(picks)} value bets ({len(ml_picks)} from ML model)")

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
            conf_tag = {"High": "[H]", "Medium": "[M]", "Low": "[L]"}.get(pick.get("confidence", ""), "[?]")

            print(f"\n{conf_tag} #{i}: {pick['home_team']} vs {pick['away_team']} [ML]")
            print(f"   Liga: {pick['league']}")
            print(f"   Tid: {pick['kickoff']}")

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

            model_prob = pick.get('model_prob')
            if model_prob:
                print(f"   Modell: {model_prob:.1%}")

            edge = pick.get('edge')
            if edge is not None:
                print(f"   Edge: {edge:.1%}")

    # Summary
    print()
    print("=" * 60)
    if picks:
        picks_with_edge = [p for p in picks if p.get('edge') is not None]
        if picks_with_edge:
            total_stake = len(picks_with_edge) * 10
            avg_edge = sum(p['edge'] for p in picks_with_edge) / len(picks_with_edge)
            print(f"Draw-bets med edge: {len(picks_with_edge)} bets a 10 kr = {total_stake} kr")
            print(f"Gjennomsnittlig edge: {avg_edge:.1%}")

        btts_picks = [p for p in picks if p['market'] == 'BTTS']
        if btts_picks:
            print(f"BTTS-tips (uten NT-odds): {len(btts_picks)} kamper")
            print("  (Finn egne odds hos bookmaker for å beregne edge)")


if __name__ == "__main__":
    main()
