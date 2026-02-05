#!/usr/bin/env python3
"""
Hent og vis dagens fotballkamper med odds fra Norsk Tipping.

Usage:
    python scripts/get_todays_odds.py [--date YYYY-MM-DD] [--all] [--json]

Options:
    --date    Vis kamper for en spesifikk dato (default: i dag)
    --all     Vis alle kommende kamper, ikke bare dagens
    --json    Output som JSON i stedet for tabell
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import date, datetime, timedelta

# Legg til src i path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.norsk_tipping_client import NorskTippingClient, NorskTippingMatch


def format_probability(prob: float | None) -> str:
    """Formater sannsynlighet til visningsformat"""
    if prob is None:
        return "  -  "
    return f"{prob:4.0f}%"


def probability_to_odds(prob: float | None) -> str:
    """Konverter sannsynlighet til desimalodds"""
    if prob is None or prob == 0:
        return "  -  "
    odds = 100 / prob
    return f"{odds:5.2f}"


def print_matches_table(matches: list[NorskTippingMatch], show_odds: bool = True):
    """Skriv ut kamper som en formatert tabell"""
    if not matches:
        print("Ingen kamper funnet.")
        return

    # Sorter etter kickoff
    matches = sorted(matches, key=lambda m: m.kickoff)

    # Grupper etter dato
    matches_by_date: dict[date, list[NorskTippingMatch]] = {}
    for match in matches:
        match_date = match.kickoff.date()
        if match_date not in matches_by_date:
            matches_by_date[match_date] = []
        matches_by_date[match_date].append(match)

    # Skriv ut
    for match_date, date_matches in matches_by_date.items():
        weekday = ["Man", "Tir", "Ons", "Tor", "Fre", "Lor", "Son"][match_date.weekday()]
        print(f"\n{'=' * 90}")
        print(f" {weekday} {match_date.strftime('%d.%m.%Y')}")
        print(f"{'=' * 90}")

        if show_odds:
            print(f"{'Tid':<6} {'Hjemme':<20} {'Borte':<20} {'Liga':<20} {'H':>5} {'U':>5} {'B':>5}")
            print("-" * 90)
        else:
            print(f"{'Tid':<6} {'Hjemme':<25} {'Borte':<25} {'Liga':<30}")
            print("-" * 90)

        for match in date_matches:
            time_str = match.kickoff.strftime("%H:%M")
            home = match.home_team[:19]
            away = match.away_team[:19]
            league = match.league[:19]

            if show_odds and match.home_win_probability:
                h_prob = format_probability(match.home_win_probability)
                d_prob = format_probability(match.draw_probability)
                a_prob = format_probability(match.away_win_probability)
                print(f"{time_str:<6} {home:<20} {away:<20} {league:<20} {h_prob:>5} {d_prob:>5} {a_prob:>5}")
            else:
                home = match.home_team[:24]
                away = match.away_team[:24]
                league = match.league[:29]
                print(f"{time_str:<6} {home:<25} {away:<25} {league:<30}")

    print(f"\nTotalt: {len(matches)} kamper")


def print_matches_detailed(matches: list[NorskTippingMatch]):
    """Skriv ut kamper med detaljert informasjon inkludert odds"""
    if not matches:
        print("Ingen kamper funnet.")
        return

    matches = sorted(matches, key=lambda m: m.kickoff)

    print("\n" + "=" * 80)
    print(" KOMMENDE KAMPER MED ODDS FRA NORSK TIPPING")
    print("=" * 80)

    for match in matches:
        print(f"\n{match.kickoff.strftime('%a %d.%m %H:%M')} - {match.league}")
        print(f"  {match.home_team} vs {match.away_team}")

        if match.home_win_probability:
            print(f"  Sannsynligheter: H: {match.home_win_probability}% | U: {match.draw_probability}% | B: {match.away_win_probability}%")

            # Beregn implisitte odds
            h_odds = 100 / match.home_win_probability if match.home_win_probability else 0
            d_odds = 100 / match.draw_probability if match.draw_probability else 0
            a_odds = 100 / match.away_win_probability if match.away_win_probability else 0
            print(f"  Implisitt odds:   H: {h_odds:.2f} | U: {d_odds:.2f} | B: {a_odds:.2f}")
        else:
            print("  Odds: Ikke tilgjengelig")

    print(f"\n{'=' * 80}")
    print(f"Totalt: {len(matches)} kamper")


def print_matches_json(matches: list[NorskTippingMatch]):
    """Output matches as JSON"""
    output = [match.to_dict() for match in matches]
    print(json.dumps(output, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(
        description="Hent og vis fotballkamper med odds fra Norsk Tipping"
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Vis kamper for en spesifikk dato (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Vis alle kommende kamper"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output som JSON"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Vis detaljert informasjon"
    )
    args = parser.parse_args()

    # Initialiser klient
    client = NorskTippingClient()

    print("Henter data fra Norsk Tipping...")

    # Hent kamper
    if args.all:
        matches = client.get_upcoming_football_matches()
    elif args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"Ugyldig datoformat: {args.date}. Bruk YYYY-MM-DD.")
            sys.exit(1)
        matches = client.get_football_matches_for_date(target_date)
    else:
        # Standard: vis alle kommende kamper siden "i dag" ofte er tomt
        matches = client.get_upcoming_football_matches()

    # Output
    if args.json:
        print_matches_json(matches)
    elif args.detailed:
        print_matches_detailed(matches)
    else:
        print_matches_table(matches)


if __name__ == "__main__":
    main()
