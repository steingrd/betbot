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
│   └── match_predictor.pkl # Trent XGBoost-modell
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
    ├── run_backtest.py             # Kjør backtest
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

### Kjør backtest
```bash
python scripts/run_backtest.py
```

### Se dagens odds
```bash
python scripts/get_todays_odds.py
python scripts/get_todays_odds.py --date 2026-02-08
python scripts/get_todays_odds.py --detailed
```

### Tren modell på nytt
```bash
python src/models/match_predictor.py
```

## Kjente problemer

1. **FootyStats cache**: Etter å velge ligaer må man vente 30 min før data er tilgjengelig.
2. **Norsk Tipping**: Bruker Tipping-kuponger (sannsynligheter), ikke faktiske bookmakerodds.
3. **Backtest er in-sample**: Trenger tidsbasert split for realistiske resultater.

## Viktig ved endringer

- **Oppdater SYSTEM.md** hvis du endrer datamodell, features, eller modellarkitektur
- **Oppdater PLAN.md** hvis du fullfører eller legger til oppgaver
- **Oppdater DATA_ANALYSIS.md** hvis du tar i bruk nye felter
