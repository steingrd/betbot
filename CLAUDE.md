# BetBot

ML-system for value bets i fotball. Sammenligner prediksjoner fra 4 strategier med odds fra Norsk Tipping.

## Arkitektur

- **Backend**: FastAPI (`src/api/`) med SSE for task-progress
- **Frontend**: React + Vite + Tailwind (`web/`) med shadcn/ui
- **Strategier**: XGBoost, Poisson/Dixon-Coles, Elo, LogReg (`src/strategies/`)
- **Consensus**: Per-market stemmegivning på tvers av strategier (`src/strategies/consensus.py`)
- **Data**: FootyStats API + Norsk Tipping API -> SQLite (`data/processed/betbot.db`)

## Nøkkelmoduler

| Mappe | Innhold |
|---|---|
| `src/strategies/` | 4 strategier med felles protokoll (`base.py`): `train()`, `predict()`, `save()`, `load()` |
| `src/features/` | Feature-generering fra historiske kampdata |
| `src/data/` | API-klienter (FootyStats, Norsk Tipping), data-prosessering, bet-repository |
| `src/analysis/` | ValueBetFinder - identifiserer value bets |
| `src/predictions/` | DailyPicksFinder - dagens tips med consensus |
| `src/services/tasks.py` | Bakgrunnsjobber (download, train, predict) |
| `src/api/` | FastAPI routes og task manager |
| `src/chat/` | LLM-integrasjon (Anthropic/OpenAI) med chat-historikk |
| `scripts/` | CLI-verktoy for nedlasting, trening, backtest, odds |

## Konvensjoner

- Python 3.11+, `.venv/`, API-nokkler i `.env`
- Features beregnes KUN fra data tilgjengelig FOR kampen (unnga data leakage)
- Modeller lagres i `models/` som `{slug}.pkl` (xgboost, logreg) eller `{slug}.json` (poisson, elo)
- Aldri commit `.env` eller `data/`

## Vanlige kommandoer

```bash
python scripts/download_all_leagues.py   # Last ned data
python scripts/train_model.py            # Tren alle strategier
python scripts/run_backtest.py           # Out-of-sample backtest
python scripts/run_web.py                # Start web-app
python scripts/get_todays_odds.py        # Hent odds fra Norsk Tipping
```

## Sesong-handtering

- Per-league holdout i backtest (ikke globalt)
- Bruker `season_id` fra FootyStats, ingen maned-heuristikk
- Stotter bade kalenderar (Norge: "2024") og Aug-Mai ("2024/2025")
