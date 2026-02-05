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

### Fase 5: Produksjon ⬅️ NESTE
- [ ] Velg ligaer i FootyStats dashboard
- [ ] Last ned flere sesonger (3-5 per liga)
- [ ] Retrain modell på større datasett
- [ ] Sette opp daglig kjøring

### Fase 6: Live Odds Integration
- [ ] Integrere med odds-api.com eller lignende
- [ ] Real-time value bet alerts
- [ ] Automatisk tracking av bets

### Fase 7: LLM Integration
- [ ] Bruke Claude til å forklare prediksjoner
- [ ] Analysere uventede mønstre
- [ ] Generere daglige rapporter

## Bruk

```bash
# Test API
python scripts/test_api.py

# Last ned data
python scripts/download_data.py

# Kjør backtest
python scripts/run_backtest.py
```

## Prosjektstruktur

```
betbot/
├── data/
│   ├── raw/           # Rå API-data
│   └── processed/     # SQLite DB og CSV
├── models/            # Trente modeller (.pkl)
├── src/
│   ├── data/          # API client og data processing
│   ├── features/      # Feature engineering
│   ├── models/        # ML modeller
│   └── analysis/      # Value bet detection
└── scripts/           # Kjørbare scripts
```

## Notater
- Free Trial key krever at man velger ligaer i dashboard
- Example key gir tilgang til PL 2018/2019 for testing
- Backtest viser lovende resultater, men trenger validering på ut-av-sample data
