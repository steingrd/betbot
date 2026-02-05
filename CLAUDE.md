# BetBot - Claude Code Instruksjoner

## Prosjektoversikt

ML-basert system for å identifisere value bets i fotball. Bruker historisk data fra FootyStats API og sammenligner med odds fra Norsk Tipping.

## Viktige filer å lese først

1. **SYSTEM.md** - Fullstendig systemdokumentasjon (arkitektur, data, modeller)
2. **PLAN.md** - Prosjektplan og status
3. **DATA_ANALYSIS.md** - Analyse av tilgjengelige data og forbedringsmuligheter

## Prosjektstruktur

```
betbot/
├── data/
│   ├── raw/api_cache/     # Cached API-responses
│   └── processed/
│       ├── betbot.db      # SQLite database med kampdata
│       └── features.csv   # Genererte features
├── models/
│   ├── match_predictor.pkl           # Trent XGBoost-modell (current)
│   └── match_predictor_YYYYMMDD_*.pkl # Versjonerte modeller
├── reports/
│   ├── latest_training_report.json   # Siste treningsrapport
│   └── training_report_*.json        # Historiske rapporter
├── src/
│   ├── data/
│   │   ├── footystats_client.py    # FootyStats API-klient
│   │   ├── norsk_tipping_client.py # Norsk Tipping API-klient
│   │   └── data_processor.py       # Data til SQLite
│   ├── features/
│   │   └── feature_engineering.py  # Feature-generering
│   ├── models/
│   │   └── match_predictor.py      # ML-modeller (XGBoost)
│   └── analysis/
│       └── value_finder.py         # Value bet detection
└── scripts/
    ├── test_api.py                 # Test FootyStats API
    ├── download_all_leagues.py     # Last ned alle valgte ligaer
    ├── train_model.py              # Tren modeller med progress
    ├── run_backtest.py             # Kjør backtest
    ├── daily_picks.py              # Finn value bets
    └── get_todays_odds.py          # Hent odds fra Norsk Tipping
```

## Konvensjoner

### Kode
- Python 3.11+
- Alle scripts importerer fra `src/` via `sys.path.insert`
- API-klienter har innebygd caching og rate limiting
- Features beregnes KUN fra data tilgjengelig FØR kampen (unngå data leakage)

### Data
- SQLite database i `data/processed/betbot.db`
- API-cache i `data/raw/api_cache/` (24 timers TTL)
- Features lagres også som CSV for enkel inspeksjon

### Miljø
- Virtual environment: `.venv/`
- API-nøkler i `.env` (FOOTYSTATS_API_KEY)
- Aldri commit `.env` eller `data/` innhold

## Vanlige oppgaver

### Last ned data
```bash
source .venv/bin/activate
python scripts/download_all_leagues.py
```

### Kjør backtest (out-of-sample med per-league holdout)
```bash
python scripts/run_backtest.py                    # Default: hold-out siste sesong per liga
python scripts/run_backtest.py --holdout-seasons 2 # Hold ut 2 sesonger per liga
python scripts/run_backtest.py --in-sample         # In-sample (kun for referanse)
```

**Merk:** Backtest krever sesong-metadata i databasen. Kjør `download_all_leagues.py` for å populere dette.

### Backfill sesong-metadata (for eksisterende data)
```bash
python scripts/backfill_seasons.py   # Oppdater seasons-tabell med liga-info
```

### Se dagens odds
```bash
python scripts/get_todays_odds.py
python scripts/get_todays_odds.py --date 2026-02-08
python scripts/get_todays_odds.py --detailed
```

### Tren modell på nytt
```bash
python scripts/train_model.py
```

## Kjente problemer

1. **FootyStats cache**: Etter å velge ligaer må man vente 30 min før data er tilgjengelig.
2. **Norsk Tipping**: Bruker Tipping-kuponger (sannsynligheter), ikke faktiske bookmakerodds.

## Sesong-håndtering

Systemet støtter både kalenderår-sesonger (Norge) og Aug-Mai sesonger (Premier League):

- **Per-league holdout**: Backtest holder ut siste N sesonger *per liga*, ikke globalt
- **Ingen måned-heuristikk**: Bruker `season_id` og faktiske kampdatoer fra FootyStats
- **Automatisk sesong-label**: "2024" for kalenderår, "2024/2025" for Aug-Mai
- **Leakage-verifisering**: Sjekker at max(train_date) < min(test_date) per liga

## Viktig ved endringer

- **Oppdater SYSTEM.md** hvis du endrer datamodell, features, eller modellarkitektur
- **Oppdater PLAN.md** hvis du fullfører eller legger til oppgaver
- **Oppdater DATA_ANALYSIS.md** hvis du tar i bruk nye felter
