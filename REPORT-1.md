# REPORT-1

## Code review: modellsvakheter og forbedringsforslag

Dato: 2026-02-26  
Scope: gjennomgang av trening, feature engineering, backtest og live-prediksjon (daily picks).

## Metode
- Lest kjernekode i `src/models`, `src/features`, `src/analysis`, `src/predictions`, `src/data` og relevante scripts.
- Verifisert sammenheng mellom trening (`scripts/train_model.py`), backtest (`scripts/run_backtest.py`) og live prediksjon (`src/predictions/daily_picks.py`).
- Ikke kjørt full trening/backtest lokalt i denne workspacen fordi miljøet mangler installert `xgboost`.

## Funn (prioritert)

### Kritisk

1. **Alvorlig train/serve mismatch i live-pipeline (`daily_picks`)**
- Referanser: `src/predictions/daily_picks.py:210-263`, `src/models/match_predictor.py:75-110`, `src/features/feature_engineering.py:328-427`
- Problem: live-features bygges med en annen logikk enn trenings-features.
- Eksempler:
  - `h2h_*` settes hardkodet til `0`.
  - `home_attack_quality`/`away_attack_quality` settes hardkodet til `0.3`.
  - `fs_*_potential` settes hardkodet til `50/50/30`.
  - sesongfelt (`position`, `season_points`, `season_gd`) defaultes i praksis til konstante verdier.
- Konsekvens: modellen scorer på feature-distribusjoner den ikke ble trent på. Dette kan gi systematisk feilkalibrerte sannsynligheter og falske “value”-signaler.

2. **`position_diff` har motsatt fortegn i live vs trening**
- Referanser: `src/features/feature_engineering.py:366`, `src/predictions/daily_picks.py:239`
- Problem: trening bruker `away_position - home_position` (positiv = hjemmelag bedre), live bruker `home - away`.
- Konsekvens: modellen får feil retning på en sentral feature i produksjon.

### Høy

3. **Away venue-statistikk i live blir feilberegnet**
- Referanse: `src/predictions/daily_picks.py:307-320`
- Problem: `_compute_form()` samler `venue_*` kun når laget er hjemme (`if is_home:`), men output brukes både for home- og away-features.
- Konsekvens: `away_venue_*` representerer ikke bortestyrke, men en blanding/feil proxy.

4. **"Siste 10 kamper" i live er ikke garantert siste 10 i tid**
- Referanser: `src/data/data_processor.py:336-347`, `src/predictions/daily_picks.py:193-199`
- Problem: `load_matches()` mangler `ORDER BY date_unix`, men `tail(10)` brukes som om data er tids-sortert.
- Konsekvens: form-features i live kan baseres på vilkårlig rekkefølge.

5. **Feil i prediksjonsflyt skjules av broad exception**
- Referanse: `src/predictions/daily_picks.py:353-391`
- Problem: `except Exception: pass` under model inference.
- Konsekvens: stille feil, manglende picks, vanskelig feilsøking, risiko for at produksjon “ser OK ut” mens modellen feiler.

6. **Feature-cache invalidasjon er for svak**
- Referanse: `scripts/train_model.py:136-147`
- Problem: cache valideres kun på kolonnenavn (`expected_cols`), ikke på featurelogikk/version/hash.
- Konsekvens: endret feature-beregning kan bruke stale features uten varsel, og gi inkonsistent trening/backtest over tid.

7. **Norsk Tipping-kilden er ikke faktisk oddsfeed i praksis**
- Referanser: `src/data/norsk_tipping_client.py:274-294`, `src/data/norsk_tipping_client.py:331-347`, `src/predictions/daily_picks.py:139-147`
- Problem:
  - OddsenGameInfo-parsing er ikke implementert (`pass`).
  - fallback bruker tippe-sannsynligheter (`expert`/`peoples`) og konverterer til pseudo-odds (`100/prob`).
- Konsekvens: “edge” måles mot tipsfordeling, ikke nødvendigvis markedsodds. Value-begrepet blir metodisk svakt.

### Medium

8. **Backtest-CI undervurderer usikkerhet**
- Referanse: `scripts/run_backtest.py:56-89`
- Problem: bootstrap sampler på bet-nivå antar uavhengighet mellom bets, selv når flere bets kan komme fra samme kamp/markedssjokk.
- Konsekvens: for smale konfidensintervaller og overtro på ROI-estimat.

9. **Holdout-logikk kan gi tom train-del per liga ved høy `--holdout-seasons`**
- Referanse: `scripts/run_backtest.py:185-205`
- Problem: kun `<2` sesonger advares; ved f.eks. 2 sesonger og `holdout=2` blir train tom for den ligaen uten eksplisitt guardrail.
- Konsekvens: ustabil generalisering og vanskelig tolkning av per-liga-resultater.

10. **Dokumentasjonsdrift rundt modell/evaluering**
- Referanser: `SYSTEM.md:245`, `SYSTEM.md:423`, `src/models/match_predictor.py:305-342`, `scripts/run_backtest.py:360-565`
- Problem: dokument beskriver gammel kalibrering/backtest-regime som ikke matcher implementasjonen.
- Konsekvens: feil beslutningsgrunnlag ved videreutvikling.

## Modellsvakheter (overordnet)

1. **Produksjonsfeatures er ikke den samme funksjonen som treningsfeatures** (største tekniske risiko).
2. **Målestokk for “value” i live er svak** når pseudo-odds brukes i stedet for faktisk bookmaker-pris.
3. **Separate modeller (1X2, O2.5, BTTS) uten konsistenslag** kan gi intern usammenheng i sannsynligheter.
4. **Cache og evalueringsregime kan gi falsk trygghet** uten streng versjonering og robust OOS-rutine.

## Anbefalt forbedringsplan

### Fase 1 (haster)
1. Bygg live-features via samme feature-engine som trening (felles funksjon/API, ikke duplisert heuristikk).
2. Rett `position_diff`-fortegn i live.
3. Fjern broad `except` i inference; logg og tell feil eksplisitt.
4. Tving tids-sortering ved datauttak (`ORDER BY date_unix`) eller sortering før `tail()`.

### Fase 2 (neste iterasjon)
1. Innfør cache-versionering med feature-hash (kodeversjon + parametre + datastempel).
2. Implementer reell OddsenGameInfo-parsing og bruk faktiske odds når tilgjengelig.
3. Oppgrader backtest-CI med blokk-bootstrap per kampdato eller per kamp-id.
4. Legg på guardrails i split-funksjonen (`min_train_seasons >= 1`).

### Fase 3 (modellforbedringer)
1. Innfør walk-forward validering med tidsvinduer og per-liga rapportering.
2. Test probabilistisk målmodell (Poisson/bivariat Poisson) for konsistente markedsprobabiliteter.
3. Bruk tidsvekting/concept-drift-håndtering (nyere sesonger høyere vekt).
4. Benchmark alltid mot marked-baseline (log loss/Brier/ROI delta vs implied probs).

## Konklusjon
Kjernen i trenings- og backtestløpet er betydelig bedre enn tidligere MVP-oppsett, men dagens live-pipeline (`daily_picks`) har kritiske avvik fra treningsregimet. Det er den største kilden til modellrisiko nå. Før videre optimalisering bør train/serve-paritet og oddsgrunnlag ryddes opp.
