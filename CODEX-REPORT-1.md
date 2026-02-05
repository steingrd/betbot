# CODEX-REPORT-1

## Oppsummering
BetBot er dokumentert som et ML-basert system for å finne value bets i fotball ved å kombinere FootyStats-data, feature engineering, XGBoost-modeller og sammenligning mot odds (inkludert Norsk Tipping). Koden i repoet matcher i stor grad plan og systemdokumentasjon, og viser en gjennomført MVP-pipeline fra datainnsamling til backtest.

## Hva Claude Code ser ut til å ha levert
- Prosjektdokumentasjon og retning:
  - `PLAN.md` med faser, status og neste steg.
  - `SYSTEM.md` som beskriver arkitektur, datamodell, features, modeller, value-bet-logikk og risikoer.
  - `DATA_ANALYSIS.md` som analyserer FootyStats-felter og foreslår nye features/markeder.
  - `CLAUDE.md` med “operational notes” og kjøreoppskrift.
- Kjernekomponenter i pipeline:
  - FootyStats-klient med caching og rate limiting: `src/data/footystats_client.py`.
  - Dataprosessering til SQLite med utvidet schema: `src/data/data_processor.py`.
  - Feature engineering med lekkasjebeskyttelse og pre-match felter: `src/features/feature_engineering.py`.
  - Modelltrening (XGBoost + kalibrering) for 1X2, Over 2.5 og BTTS: `src/models/match_predictor.py`.
  - Value-bet-finner og backtesting: `src/analysis/value_finder.py`.
  - Norsk Tipping API-klient med matching og caching: `src/data/norsk_tipping_client.py`.
- Kjørbare scripts for datanedlasting, backtest og odds: `scripts/`.

## Styrker
- God systematikk og dokumentasjon som er lett å navigere.
- Bevissthet om data leakage og bruk av pre-match-felter (konkret implementert i data/feature-laget).
- Tydelig, modulær arkitektur som gjør det lett å utvide med nye ligaer/markeder.
- Praktisk pipeline som faktisk kan kjøres end-to-end (MVP-verdifullt).

## Konstruktive tilbakemeldinger og forbedringspunkter
1. Tidsbasert evaluering mangler i praksis
   - `src/models/match_predictor.py` bruker tilfeldig `train_test_split`. Det gir overly optimistisk resultat når data har tidsstruktur.
   - Forslag: implementer walk-forward eller “train on seasons, test on next season” og rapporter out-of-sample resultater.

2. Backtest er in-sample
   - `scripts/run_backtest.py` og `src/analysis/value_finder.py` evaluerer samme sesong som trenes på.
   - Forslag: tren på tidligere sesonger og backtest på en helt hold-out sesong (eller bruk rolling-window).

3. Standings/posisjon kan bli feil ved flere sesonger
   - `FeatureEngineer._get_season_position` bruker alle kamper før dato uten å filtrere på `season_id`.
   - Ved flere sesonger vil tabellposisjoner bli feil.
   - Forslag: filter på `season_id` (og evt. liga) for alle season-baserte features.

4. Overround/margin i odds håndteres ikke
   - `ValueBetFinder` bruker `1/odds` direkte. Bookmaker-margins gir sum sannsynlighet > 1.
   - Forslag: normaliser implied probabilities per marked (1X2) eller estimer overround.

5. Dokumentasjon er delvis ute av sync
   - `CLAUDE.md` sier at `home_ppg/away_ppg` gir leakage, men koden bruker allerede `pre_match_*`.
   - Forslag: oppdater `CLAUDE.md` og evt. `SYSTEM.md` slik at “Known issues” matcher faktisk status.

6. Reproduserbarhet og drift
   - Det finnes ingen enkel “pipeline script” som kjører hele flyten på en deterministisk måte med tidsbasert split.
   - Forslag: legg til et `scripts/train_model.py` som låser seeds, logger metrics og skriver modellversjon.

7. Repo hygiene
   - `src/**/__pycache__` ligger i repoet. Dette bør normalt ignoreres.
   - Forslag: legg til `__pycache__/` i `.gitignore` og fjern allerede sjekkede filer.

## Konklusjon
Claude Code har levert en komplett MVP med tydelig dokumentasjon og fungerende pipeline. Den største verdien fremover ligger i robust evaluering (tidsbasert, out-of-sample), klarere odds-justeringer, og små, men viktige forbedringer i feature-logikk og dokumentasjonskonsistens.

## TODO-liste for Claude Code
1. Bytt til tidsbasert split (walk-forward eller sesongbasert hold-out) i treningsløpet (`src/models/match_predictor.py`).
2. Lag en out-of-sample backtest (train tidligere sesonger, test på en ny) i backtestflyten (`scripts/run_backtest.py`).
3. Filtrer tabellposisjon og sesongstatistikk på `season_id` i `FeatureEngineer` for å unngå kryss-sesong-lekkasje (`src/features/feature_engineering.py`).
4. Normaliser implied probabilities for 1X2-markedet for å håndtere overround før edge-beregning (`src/analysis/value_finder.py`).
5. Oppdater “Known issues” i `CLAUDE.md` så den matcher faktisk implementasjon og fjern utdatert leakage-note.
6. Legg til et deterministisk treningsscript med seeds, logging og modellversjonering (`scripts/train_model.py`).
7. Legg til `__pycache__/` i `.gitignore` og rydd ut cache-filer som allerede ligger i repoet.
8. Legg inn en enkel evalueringsrapport som lagres per kjøring (f.eks. metrics + dato) for sporbarhet.
