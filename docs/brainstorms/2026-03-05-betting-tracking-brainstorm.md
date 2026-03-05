---
date: 2026-03-05
topic: betting-tracking
---

# Betting Tracking - Spor innsats og gevinst

## Hva vi bygger

Et komplett system for a spore plasserte spill, med modal for innsatsregistrering direkte fra value bets og kombispill, automatisk resultatsporing nar kampresultater lastes ned, og dashboard-paneler for aktive spill og totalregnskap.

## Viktige beslutninger

- **En database**: Alt lagres i `betbot.db` (samme som kampdata)
- **Flat liste**: Kuponger-fanen viser en rad per spill, inkludert kombispill (med legs)
- **Odds-justering**: Modal pre-fyller odds fra prediksjon, bruker kan justere til faktisk NT-odds
- **Ingen multi-bookmaker**: Kun Norsk Tipping, sa bare ett odds-felt
- **Kompakte kort**: "Aktive spill" og "Totalregnskap" som sma kort ved siden av eksisterende metrics

## Datamodell

### Ny tabell: `placed_bets`

| Kolonne | Type | Beskrivelse |
|---------|------|-------------|
| id | INTEGER PK | Auto-increment |
| match_id | TEXT | Kobling til kamp (kan vaere null for kombispill) |
| bet_type | TEXT | 'single' eller 'accumulator' |
| market | TEXT | Home/Draw/Away/Over 2.5/BTTS (null for kombispill) |
| home_team | TEXT | Hjemmelag (null for kombispill) |
| away_team | TEXT | Bortelag (null for kombispill) |
| kickoff | TEXT | Avspark ISO-format (siste kamp for kombi) |
| league | TEXT | Liga |
| odds | REAL | Faktisk odds plassert (justert i modal) |
| amount | REAL | Innsats i kroner |
| model_prob | REAL | Modellens sannsynlighet |
| edge | REAL | Edge ved plassering |
| consensus_count | INTEGER | Antall strategier enige |
| status | TEXT | 'pending', 'won', 'lost', 'cancelled' |
| payout | REAL | Utbetaling (odds * amount hvis vunnet, 0 hvis tapt, null hvis pending) |
| profit | REAL | payout - amount (null hvis pending) |
| settled_at | TEXT | Tidspunkt for oppgjor |
| created_at | TEXT | Tidspunkt for plassering |

### Ny tabell: `accumulator_legs`

| Kolonne | Type | Beskrivelse |
|---------|------|-------------|
| id | INTEGER PK | Auto-increment |
| bet_id | INTEGER FK | Referanse til placed_bets.id |
| match_id | TEXT | Kamp-ID |
| market | TEXT | Home/Draw/Away/Over 2.5/BTTS |
| home_team | TEXT | Hjemmelag |
| away_team | TEXT | Bortelag |
| kickoff | TEXT | Avspark |
| odds | REAL | Enkeltkamp-odds for dette benet |
| result | TEXT | 'pending', 'won', 'lost' |

## UI-komponenter

### 1. Innsats-modal (fra Value Bets og Kombispill)

- Klikk pa rad -> modal apnes
- Pre-fylt med: lag, marked, odds fra prediksjon
- Odds-felt: redigerbart for a justere til faktisk NT-odds
- Hurtigvalg-knapper: 10 kr, 25 kr, 50 kr, 100 kr
- Mulig gevinst vises live (odds * innsats)
- "Plasser spill"-knapp lagrer til database

For kombispill: viser alle legs med samlet odds, kun innsats og odds-justering.

### 2. Radmarkering i Value Bets / Kombispill

- Rader med plassert spill far en annen bakgrunnsfarge (f.eks. svak gronn/bla)
- Liten indikator (ikon eller badge) som viser at spill er plassert
- Krever at frontend sjekker placed_bets ved lasting av prediksjoner

### 3. Ny fane: "Kuponger"

- Tabell med alle plasserte spill, nyeste forst
- Kolonner: Dato, Kamp/Beskrivelse, Marked, Odds, Innsats, Status, Gevinst
- Kombispill viser "Kombi (3 kamper)" med expand for a se legs
- Filtrering: Alle / Aktive / Avgjorte / Vunnet / Tapt
- Fargekoding: gronn for vunnet, rod for tapt, gul/noytral for pending

### 4. Kompakt kort: "Aktive spill"

- Antall uavgjorte spill
- Total innsats i spill na
- Plasseres ved siden av eksisterende DataQuality-kort

### 5. Kompakt kort: "Totalregnskap"

- Total innsats (alle tider)
- Total gevinst
- Netto P&L (med farge: gronn/rod)
- ROI%
- Plasseres ved siden av "Aktive spill"

## Automatisk resultatsporing

Nar `/download` kjores og nye resultater kommer inn:

1. Finn alle `placed_bets` med status='pending'
2. For single bets: match pa match_id, sjekk resultat mot market
3. For accumulators: sjekk hver leg, kombispill vunnet kun hvis alle legs vunnet
4. Oppdater status, payout, profit, settled_at
5. Post event/notifikasjon om avgjorte spill

## API-endepunkter

| Metode | Sti | Beskrivelse |
|--------|-----|-------------|
| POST | /api/bets | Plasser nytt spill |
| GET | /api/bets | Liste over spill (med filter: status, limit) |
| GET | /api/bets/summary | Aktive spill + totalregnskap |
| GET | /api/bets/placed-matches | Liste av match_id+market som er spilt pa (for radmarkering) |
| DELETE | /api/bets/{id} | Kanseller spill (sett status=cancelled) |

## Neste steg

-> `/workflows:plan` for implementasjonsdetaljer og filendringer
