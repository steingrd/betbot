# BetBot - Prosjektplan

## Mål
Bygge et ML-basert system for å identifisere value bets i fotball.

## Arkitektur

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Data Samling   │────▶│  ML Modeller     │────▶│  Odds Analyse   │
│  (footystats)   │     │  (XGBoost etc)   │     │  (value bets)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                        │                        │
        ▼                        ▼                        ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Feature Eng.   │     │  Model Training  │     │  LLM Analyse    │
│  (statistikk)   │     │  & Validation    │     │  (forklaringer) │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## Status: MVP FERDIG ✓

### Fase 1: Data Foundation ✓ FERDIG
- [x] Undersøke footystats.org API/data tilgang
- [x] Sette opp data scraping/download (FootyStatsClient med caching)
- [x] Definere datamodell (SQLite)
- [x] Laste ned testdata (PL 2018/2019, 380 kamper)

### Fase 2: Feature Engineering ✓ FERDIG
- [x] Lag-statistikk (form, hjemme/borte, mål for/mot)
- [x] Head-to-head historikk
- [x] Sesongposisjon og poeng
- [x] xG-baserte features

### Fase 3: Modellering ✓ FERDIG
- [x] XGBoost modell for 1X2 (55.7% accuracy)
- [x] XGBoost modell for Over 2.5
- [x] XGBoost modell for BTTS
- [x] Kalibrering av sannsynligheter

### Fase 4: Value Bet Detection ✓ FERDIG
- [x] Sammenligne modell-sannsynlighet vs implied odds
- [x] Edge-beregning og value bet identifisering
- [x] Kelly criterion for innsats-sizing
- [x] Backtesting system

## Backtest Resultater (PL 2018/2019)

| Min Edge | Bets | Win Rate | ROI |
|----------|------|----------|-----|
| 3%       | 397  | 48.4%    | +39.2% |
| 5%       | 332  | 51.2%    | +51.8% |
| 8%       | 234  | 57.3%    | +82.2% |
| 10%      | 197  | 61.4%    | +100.6% |

**Beste markeder:** Away (+157% ROI), Home (+78% ROI)
**Unngå:** Draw, BTTS (negative ROI)

## Neste Steg

### Fase 5: TUI Dashboard ✓ FERDIG
- [x] Textual-basert TUI med multi-panel layout (Predictions, Data, Trening tabs)
- [x] TaskQueue med bakgrunnsnedlasting av ligadata
- [x] Modelltrening med progress bar i TUI
- [x] Predictions-workflow med value bet-tabell
- [x] LLM-integrasjon med streaming chat (Anthropic/OpenAI)
- [x] Ende-til-ende testing og polish

### Fase 6: Live Odds Integration
- [ ] Integrere med odds-api.com eller lignende
- [ ] Real-time value bet alerts
- [ ] Automatisk tracking av bets

## Bruk

```bash
# Start TUI dashboard (anbefalt)
python scripts/run_tui.py

# CLI-scripts
python scripts/test_api.py          # Test API-tilkobling
python scripts/download_all_leagues.py  # Last ned data
python scripts/run_backtest.py      # Kjør backtest
python scripts/daily_picks.py       # Finn value bets (CLI)
python scripts/get_todays_odds.py   # Hent odds fra NT
```

## Prosjektstruktur

```
betbot/
├── data/
│   ├── raw/           # Rå API-data
│   └── processed/     # SQLite DB, features CSV, chat DB
├── models/            # Trente modeller (.pkl)
├── src/
│   ├── data/          # API-klienter og data processing
│   ├── features/      # Feature engineering
│   ├── models/        # ML-modeller
│   ├── analysis/      # Value bet detection
│   ├── predictions/   # DailyPicksFinder
│   ├── tui/           # Textual TUI dashboard
│   └── chat/          # LLM-integrasjon
└── scripts/           # Kjørbare scripts
```

## Notater
- Free Trial key krever at man velger ligaer i dashboard
- Example key gir tilgang til PL 2018/2019 for testing
- Backtest viser lovende resultater, men trenger validering på ut-av-sample data
