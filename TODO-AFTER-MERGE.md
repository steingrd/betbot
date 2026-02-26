# TODO After Merge

Mål: trene og verifisere en ny modell med oppdatert cache-logikk og live-feature fixes.

1. Klargjør miljø
```bash
cd /Users/steingrd/conductor/workspaces/betbot/boston-v1
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Oppdater data (inkludert sesong-metadata)
```bash
python scripts/download_all_leagues.py
# Hvis du har eldre DB uten komplett seasons-metadata:
python scripts/backfill_seasons.py
```

3. Tren ny modell (vil auto-invalideres hvis kilde/funksjoner er endret)
```bash
python scripts/train_model.py
```

4. Kjør out-of-sample backtest
```bash
python scripts/run_backtest.py --holdout-seasons 1
# Alternativt mer robust test:
python scripts/run_backtest.py --holdout-seasons 2 --exclude-cups
```

5. Verifiser artefakter ble produsert
- Sjekk at modell finnes i `models/match_predictor.pkl`.
- Sjekk at rapport finnes i `reports/latest_training_report.json`.
- Sjekk cache metadata i `data/processed/features.meta.json`.

6. Sanity-check live picks
```bash
python scripts/daily_picks.py --min-edge 0.05
```

7. Drift/oppfølging
- Hvis historiske data endres, kjør `python scripts/train_model.py` igjen (cache skal nå invalidere korrekt).
- Bruk `python scripts/run_backtest.py --regenerate` hvis du vil tvinge full feature-regenerering.
