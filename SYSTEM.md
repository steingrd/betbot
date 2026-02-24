# BetBot - Systemdokumentasjon

## 1. Oversikt

BetBot er et maskinlaeringssystem for a identifisere "value bets" i fotball. Systemet kombinerer historisk kampdata med ML-modeller for a estimere sannsynligheter for ulike utfall, og sammenligner disse med bookmakernes odds for a finne situasjoner hvor modellen mener oddsene er feilpriset.

### Mal

- Predikere kampresultater (1X2), Over 2.5 mal, og BTTS (begge lag scorer)
- Identifisere value bets hvor modellens sannsynlighet overstiger implied probability fra odds
- Optimalisere innsatsstorrelse via Kelly-kriteriet
- Validere strategien gjennom backtesting pa historiske data

### Arkitektur

```
FootyStats API --> DataProcessor --> FeatureEngineer --> MatchPredictor --> ValueBetFinder
      |                |                   |                   |                  |
   Radata          SQLite DB          40+ features        XGBoost x3          Edge + Kelly
```

---

## 2. Data

### Datakilde

Data hentes fra **FootyStats API** (api.football-data-api.com). APIet tilbyr detaljerte kampdata inkludert:

- Kampresultater og malstatistikk
- Skudd, hjornespark, kort, possession
- Expected Goals (xG)
- Historiske odds fra flere bookmakere

### API-haandtering

`FootyStatsClient` (src/data/footystats_client.py) haandterer:
- **Rate limiting**: Maks 0.5 requests/sekund (konservativt for hobby-tier)
- **Caching**: Responses caches lokalt i 24 timer for a spare API-kall
- **Feilhaandtering**: Automatisk retry ved feil

### Datamodell (SQLite)

Kampdata lagres i `data/processed/betbot.db` med folgende hovedfelt:

#### Identifikasjon
| Felt | Type | Beskrivelse |
|------|------|-------------|
| id | INTEGER | Unik kamp-ID fra API |
| season_id | INTEGER | Sesong-ID |
| game_week | INTEGER | Serierunde |
| date_unix | INTEGER | Kamptidspunkt (Unix timestamp) |

#### Lag
| Felt | Type | Beskrivelse |
|------|------|-------------|
| home_team_id | INTEGER | Hjemmelagets ID |
| home_team | TEXT | Hjemmelagets navn |
| away_team_id | INTEGER | Bortelagets ID |
| away_team | TEXT | Bortelagets navn |

#### Resultat
| Felt | Type | Beskrivelse |
|------|------|-------------|
| home_goals | INTEGER | Hjemmelagets mal |
| away_goals | INTEGER | Bortelagets mal |
| total_goals | INTEGER | Totalt antall mal |
| result | TEXT | H (hjemmeseier), D (uavgjort), A (borteseier) |

#### Kampstatistikk
| Felt | Type | Beskrivelse |
|------|------|-------------|
| home_shots / away_shots | INTEGER | Totalt antall skudd |
| home_shots_on_target / away_shots_on_target | INTEGER | Skudd pa mal |
| home_possession / away_possession | INTEGER | Ballbesittelse (%) |
| home_corners / away_corners | INTEGER | Hjornespark |
| home_xg / away_xg | REAL | Expected Goals |

#### Odds
| Felt | Type | Beskrivelse |
|------|------|-------------|
| odds_home | REAL | Odds for hjemmeseier |
| odds_draw | REAL | Odds for uavgjort |
| odds_away | REAL | Odds for borteseier |
| odds_over_25 | REAL | Odds for Over 2.5 mal |
| odds_btts_yes | REAL | Odds for BTTS Ja |

#### Beregnede felt
| Felt | Type | Beskrivelse |
|------|------|-------------|
| btts | INTEGER | 1 hvis begge lag scoret |
| over_25 | INTEGER | 1 hvis mer enn 2.5 mal |
| home_ppg / away_ppg | REAL | Pre-match PPG (garantert før kampen) |
| home_overall_ppg / away_overall_ppg | REAL | Overall pre-match PPG |

#### Pre-match xG
| Felt | Type | Beskrivelse |
|------|------|-------------|
| home_xg_prematch | REAL | Forventet xG for hjemmelaget pre-match |
| away_xg_prematch | REAL | Forventet xG for bortelaget pre-match |
| total_xg_prematch | REAL | Total forventet xG pre-match |

#### Angrepsstatistikk
| Felt | Type | Beskrivelse |
|------|------|-------------|
| home_attacks / away_attacks | INTEGER | Totalt antall angrep |
| home_dangerous_attacks / away_dangerous_attacks | INTEGER | Farlige angrep |

#### FootyStats potensial
| Felt | Type | Beskrivelse |
|------|------|-------------|
| fs_btts_potential | REAL | BTTS-sannsynlighet (0-100) |
| fs_o25_potential | REAL | Over 2.5 sannsynlighet |
| fs_o35_potential | REAL | Over 3.5 sannsynlighet |
| fs_corners_potential | REAL | Corner-potensial |

#### Ekstra odds
| Felt | Type | Beskrivelse |
|------|------|-------------|
| odds_over_35 | REAL | Odds for Over 3.5 mal |
| odds_over_45 | REAL | Odds for Over 4.5 mal |

### Testdata

MVP-versjonen bruker **Premier League 2018/2019** (season_id: 1625) med 380 kamper for testing og backtesting.

---

## 3. Feature Engineering

`FeatureEngineer` (src/features/feature_engineering.py) genererer prediktive features basert **utelukkende pa data tilgjengelig for kampen**.

### Formbaserte features (siste 5 kamper)

For hvert lag beregnes:

| Feature | Beskrivelse | Relevans |
|---------|-------------|----------|
| form_ppg | Poeng per kamp | Aktuell prestasjon |
| form_goals_for | Snitt mal scoret | Offensiv styrke |
| form_goals_against | Snitt mal sluppet inn | Defensiv styrke |
| form_goal_diff | Maldifferanse per kamp | Overall styrke |
| form_xg | Snitt xG | Sjansekvalitet |

### Hjemme/borte-spesifikk styrke

| Feature | Beskrivelse | Relevans |
|---------|-------------|----------|
| venue_ppg | PPG pa hjemme-/bortebane | Hjemmefordel |
| venue_goals_for | Mal scoret hjemme/borte | Venue-spesifikk angrep |
| venue_goals_against | Mal sluppet hjemme/borte | Venue-spesifikk forsvar |

### Sesongposisjon

| Feature | Beskrivelse | Relevans |
|---------|-------------|----------|
| position | Navarende tabellplassering | Lagets niva |
| season_points | Totalt antall poeng | Sesongprestasjon |
| season_gd | Maldifferanse i sesongen | Overall kvalitet |

### Head-to-head historikk (siste 5 oppgjor)

| Feature | Beskrivelse | Relevans |
|---------|-------------|----------|
| h2h_home_wins | Seire for hjemmelaget | Historisk dominans |
| h2h_draws | Antall uavgjort | Jevnbyrdighet |
| h2h_away_wins | Seire for bortelaget | Historisk dominans |
| h2h_total_goals | Snitt mal i oppgjorene | Kampens natur |

### Differansefeatures

| Feature | Beregning | Relevans |
|---------|-----------|----------|
| form_ppg_diff | home_form_ppg - away_form_ppg | Relativ form |
| position_diff | away_position - home_position | Relativ tabellposisjon |
| xg_diff | home_xg - away_xg | Relativ sjansekvalitet |

### Implied probabilities fra odds

| Feature | Beregning | Relevans |
|---------|-----------|----------|
| implied_prob_home | 1 / odds_home | Markedets vurdering |
| implied_prob_draw | 1 / odds_draw | Markedets vurdering |
| implied_prob_away | 1 / odds_away | Markedets vurdering |

### Pre-match data fra FootyStats (unngår data leakage)

| Feature | Beskrivelse | Relevans |
|---------|-------------|----------|
| home_prematch_ppg | Hjemmelagets PPG FØR kampen | Historisk styrke |
| away_prematch_ppg | Bortelagets PPG FØR kampen | Historisk styrke |
| home_overall_ppg | Hjemmelagets totale PPG pre-match | Overall styrke |
| away_overall_ppg | Bortelagets totale PPG pre-match | Overall styrke |
| prematch_ppg_diff | Differanse i pre-match PPG | Relativ styrke |

### Pre-match xG

| Feature | Beskrivelse | Relevans |
|---------|-------------|----------|
| home_xg_prematch | Forventet xG for hjemmelaget | Offensiv kvalitet |
| away_xg_prematch | Forventet xG for bortelaget | Offensiv kvalitet |
| total_xg_prematch | Total forventet xG i kampen | Mål-forventning |
| xg_prematch_diff | Differanse i pre-match xG | Relativ sjansekvalitet |

### Angrepskvalitet

| Feature | Beregning | Relevans |
|---------|-----------|----------|
| home_attack_quality | dangerous_attacks / attacks | Angrepspresisjon |
| away_attack_quality | dangerous_attacks / attacks | Angrepspresisjon |

### FootyStats potensial (ensemble features)

| Feature | Beskrivelse | Relevans |
|---------|-------------|----------|
| fs_btts_potential | FootyStats BTTS-sannsynlighet (0-100) | Ekstern modell |
| fs_o25_potential | FootyStats Over 2.5 sannsynlighet | Ekstern modell |
| fs_o35_potential | FootyStats Over 3.5 sannsynlighet | Ekstern modell |

### Hvorfor disse features?

1. **Form**: Nylig prestasjon er en sterk indikator - lag i god form fortsetter ofte a prestere
2. **Hjemmefordel**: Historisk ca. 15% hoyre sannsynlighet for hjemmeseier
3. **xG**: Bedre indikator pa "true" offensiv kvalitet enn faktiske mal (reduserer variansen)
4. **H2H**: Noen lag har psykologisk/taktisk overtak pa spesifikke motstandere
5. **Posisjon**: Lagene i toppen vinner oftere - men oddsene reflekterer dette, sa vi ser etter avvik
6. **Pre-match data**: Bruker `pre_match_*` feltene fra FootyStats for å garantere ingen data leakage
7. **Angrepskvalitet**: Ratio mellom farlige angrep og totale angrep indikerer angrepspresisjon
8. **FootyStats potensial**: Ekstern modell som ensemble-input kan fange mønstre vi ikke ser

---

## 4. ML-modeller

`MatchPredictor` (src/models/match_predictor.py) implementerer tre separate modeller:

### Modellarkitektur

Alle modeller bruker samme pipeline:

```
Features (43 stk) --> StandardScaler --> XGBoostClassifier --> CalibratedClassifierCV
```

**Kalibrering** er kritisk fordi vi trenger sannsynligheter, ikke bare prediksjoner. `CalibratedClassifierCV` sikrer at nar modellen sier 60% sannsynlighet, sa vinner faktisk ca. 60% av slike bets.

### 1X2 Resultatmodell

**Mal**: Predikere hjemmeseier (H), uavgjort (D) eller borteseier (A)

**Konfigurasjon**:
```python
XGBClassifier(
    n_estimators=100,
    max_depth=4,
    learning_rate=0.1,
    eval_metric='mlogloss'
)
```

**Ytelse**: ~55.7% accuracy (baselines: tilfeldig = 33%, alltid hjemme = ~46%)

### Over 2.5 Mal-modell

**Mal**: Predikere om kampen har mer enn 2.5 mal

**Konfigurasjon**:
```python
XGBClassifier(
    n_estimators=100,
    max_depth=3,  # Grunnere tre for a unnga overfitting
    learning_rate=0.1,
    eval_metric='logloss'
)
```

### BTTS (Both Teams To Score) Modell

**Mal**: Predikere om begge lag scorer

**Konfigurasjon**: Identisk med Over 2.5

### Feature-liste brukt i modellene

43 features brukes (odds ekskludert for a unnga "leakage"):

```python
FEATURE_COLS = [
    # Hjemmelag (11 features)
    "home_form_ppg", "home_form_goals_for", "home_form_goals_against",
    "home_form_goal_diff", "home_form_xg", "home_venue_ppg",
    "home_venue_goals_for", "home_venue_goals_against",
    "home_position", "home_season_points", "home_season_gd",

    # Bortelag (11 features)
    "away_form_ppg", "away_form_goals_for", "away_form_goals_against",
    "away_form_goal_diff", "away_form_xg", "away_venue_ppg",
    "away_venue_goals_for", "away_venue_goals_against",
    "away_position", "away_season_points", "away_season_gd",

    # Differanser (3 features)
    "form_ppg_diff", "position_diff", "xg_diff",

    # H2H (4 features)
    "h2h_home_wins", "h2h_draws", "h2h_away_wins", "h2h_total_goals",

    # Pre-match PPG fra FootyStats (5 features) - unngår data leakage
    "home_prematch_ppg", "away_prematch_ppg",
    "home_overall_ppg", "away_overall_ppg", "prematch_ppg_diff",

    # Pre-match xG (4 features)
    "home_xg_prematch", "away_xg_prematch",
    "total_xg_prematch", "xg_prematch_diff",

    # Angrepskvalitet (2 features)
    "home_attack_quality", "away_attack_quality",

    # FootyStats potensial (3 features)
    "fs_btts_potential", "fs_o25_potential", "fs_o35_potential",
]
```

### Hvorfor XGBoost?

1. **Handterer ikke-lineare sammenhenger**: Fotball har komplekse interaksjoner
2. **Robust mot overfitting**: Regularisering innebygd
3. **Feature importance**: Lett a forsta hva modellen legger vekt pa
4. **Rask trening**: Viktig for iterasjon

---

## 5. Value Bet Detection

`ValueBetFinder` (src/analysis/value_finder.py) identifiserer value bets ved a sammenligne modellens sannsynligheter med bookmakernes.

### Edge-beregning

```python
edge = model_probability - implied_probability

# Eksempel:
# Modell sier 45% sannsynlighet for borteseier
# Odds er 2.50 (implied probability = 40%)
# Edge = 0.45 - 0.40 = 0.05 (5%)
```

En **positiv edge** betyr at vi mener sannsynligheten er hoyre enn markedet priser inn.

### Filtrering av bets

Standardparametere:
- **min_edge**: 5% (bare bets med minst 5% edge)
- **min_odds**: 1.5 (unnga lave odds med lite oppside)
- **max_odds**: 8.0 (unnga ekstreme odds med hoy varians)

### Kelly Criterion

Kelly-formelen gir optimal innsatsstorrelse for a maksimere langsiktig vekst:

```python
full_kelly = (model_prob * odds - 1) / (odds - 1)
fractional_kelly = full_kelly * 0.25  # 25% av full Kelly
```

**Fractional Kelly** (25%) brukes for a redusere variansen pa bekostning av litt lavere forventet avkastning.

**Eksempel**:
- Modell: 50% sannsynlighet
- Odds: 2.20
- Full Kelly: (0.50 * 2.20 - 1) / (2.20 - 1) = 0.10 / 1.20 = 8.3%
- Fractional Kelly (25%): 2.1% av bankroll

### Markeder som evalueres

1. **Home** (1): Hjemmeseier
2. **Draw** (X): Uavgjort
3. **Away** (2): Borteseier
4. **Over 2.5**: Mer enn 2.5 mal
5. **BTTS**: Begge lag scorer

---

## 6. Backtest-resultater

Backtesten ble kjort pa Premier League 2018/2019 med flat innsats (10 kr per bet).

### Resultater etter minimum edge

| Min Edge | Antall bets | Win Rate | ROI |
|----------|-------------|----------|-----|
| 3% | 397 | 48.4% | +39.2% |
| 5% | 332 | 51.2% | +51.8% |
| 8% | 234 | 57.3% | +82.2% |
| 10% | 197 | 61.4% | +100.6% |

**Observasjon**: Hoyre edge-terskel gir faerre bets, men signifikant bedre ROI og win rate.

### Resultater per marked

| Marked | ROI |
|--------|-----|
| Away (2) | +157% |
| Home (1) | +78% |
| Draw (X) | Negativ |
| BTTS | Negativ |

**Anbefaling**: Fokuser pa 1X2-markedet, spesielt borteseier. Unnga uavgjort og BTTS.

### Tolkning

- Modellen finner reell edge i 1X2-markedet
- Borteseier-markedet ser ut til a vare mest feilpriset
- Uavgjort er notorisk vanskelig a predikere - selv med positiv edge taper vi
- BTTS/Over2.5-modellene er sannsynligvis underfittet eller markedet er mer effisient

---

## 7. Begrensninger og risiko

### Datakvalitet

- **Begrenset datasett**: Kun 380 kamper fra en sesong er for lite for robust validering
- **In-sample testing**: Backtesten kjorer pa samme data som modellen ble trent pa (80/20 split, men fortsatt samme sesong)
- **Survivorship bias**: Vi tester bare pa PL som har god datakvalitet
- **Odds-kvalitet**: Historiske odds representerer kanskje ikke det du faktisk kunne fatt

### Modellrisiko

- **Overfitting**: Med fa datapunkter og mange features er dette en reell risiko
- **Concept drift**: Fotball endrer seg over tid (taktikk, regler, VAR)
- **Feature leakage**: Selv om vi er forsiktige, kan det vare subtile former for leakage
- **Kalibreringsfeil**: Sannsynlighetene kan vare systematisk feil

### Markedsrisiko

- **Market efficiency**: Odds-markedet har blitt mer effisient over tid
- **Line movement**: Nar du plasserer bettet kan oddsene ha endret seg
- **Betting limits**: Bookmakers begrenser innsats fra vinnende spillere
- **Account restrictions**: "Gubbing" - kontoen din kan bli begrenset

### Backtesting-fallgruver

- **Unrealistisk execution**: Antar du alltid far beste odds
- **Transaksjonskostnader**: Spread og skatt er ikke inkludert
- **Psykologi**: Reell betting med ekte penger er vanskeligere enn backtest
- **Variance**: Selv med +50% ROI kan du ha lange tapsrekker

### Anbefalinger for videre utvikling

1. **Mer data**: Last ned 3-5 sesonger per liga for robust trening
2. **Out-of-sample testing**: Tren pa 2015-2018, test pa 2019
3. **Cross-validation over tid**: Walk-forward validation
4. **Flere ligaer**: Diversifiser for a redusere ligaspesifikk risiko
5. **Live odds**: Integrer med odds-API for realistisk testing
6. **Feature selection**: Bruk SHAP/importance for a redusere features
7. **Ensemble**: Kombiner XGBoost med andre modeller

---

## 8. Norsk Tipping Integrasjon

### Oversikt

Systemet henter odds fra Norsk Tipping via deres åpne API. Dette brukes for å finne value bets på kommende kamper.

### API-endepunkter

- **PoolGamesSportInfo API**: Henter Tipping-kuponger med kamper og sannsynligheter
- Sannsynlighetene er fra Norsk Tippings eksperter/publikum

### NorskTippingClient

`src/data/norsk_tipping_client.py` implementerer:

```python
client = NorskTippingClient()
matches = client.get_todays_football_matches()

for match in matches:
    print(f"{match.home_team} vs {match.away_team}")
    print(f"  H: {match.home_prob}%  U: {match.draw_prob}%  B: {match.away_prob}%")
```

### Lagnavnmatching

Klienten har innebygd fuzzy matching for å matche lagnavn mellom Norsk Tipping og FootyStats:
- "Man City" → "Manchester City"
- "Newcastle" → "Newcastle United"

### Bruk

```bash
# Vis kommende kamper
python scripts/get_todays_odds.py

# Spesifikk dato
python scripts/get_todays_odds.py --date 2026-02-08

# Detaljert med implisitte odds
python scripts/get_todays_odds.py --detailed
```

### Begrensninger

- Sannsynligheter fra Tipping (ikke faktiske bookmakerodds)
- Konverteres til odds: `odds = 100 / probability`
- Ingen historiske odds tilgjengelig

---

## 9. TUI Dashboard

### Oversikt

BetBot har et Textual-basert TUI-dashboard (`python scripts/run_tui.py`) som gir et interaktivt grensesnitt for hele pipelinen.

### Layout

Chat-first single-screen layout:

```
┌──────────────────────────┬──────────────┐
│  ChatPanel               │ DataQuality  │
│  (LLM-chat, inline       │ Panel        │
│   results, /commands,     ├──────────────┤
│   welcome message)        │ Activity     │
│                           │ Panel        │
│                           ├──────────────┤
│                           │ EventLog     │
├──────────────────────────┴──────────────┤
│  Footer                                 │
└─────────────────────────────────────────┘
```

### Chat-kommandoer

Alle handlinger utfores via `/kommandoer` i chatten:

| Kommando | Handling |
|----------|----------|
| /download | Last ned data fra FootyStats |
| /train | Tren ML-modeller |
| /predict | Finn value bets |
| /status | Oppdater datakvalitet-panelet |
| /help | Vis tilgjengelige kommandoer |
| /clear | Nullstill chat-historikk |
| Escape | Avbryt pagaende oppgave |
| Ctrl+Q | Avslutt |

Ved oppstart vises en velkomstmelding som auto-detekterer status (data, modell) og foreslaar neste steg.

### Bakgrunnsjobber

Alle tunge operasjoner kjorer i Textual workers (`@work(thread=True)`) og kommuniserer med UI via Messages:

- **Download**: Laster ned sesonger fra FootyStats med progress per sesong
- **Training**: Feature engineering + XGBoost-trening med progress bar
- **Predictions**: Henter kamper fra Norsk Tipping, finner value bets

Etter trening auto-triggres predictions, og etter predictions auto-triggres LLM-analyse.

### LLM-integrasjon

ChatPanel stotter Anthropic (Claude) og OpenAI med async streaming. Konfigureres via `.env`:
- `ANTHROPIC_API_KEY` — prioriteres forst
- `OPENAI_API_KEY` — fallback

Chat-historikk lagres i `data/processed/chat.db`.

---

## Appendix: Filstruktur

```
betbot/
├── data/
│   ├── raw/
│   │   └── api_cache/          # Cached API-responses
│   └── processed/
│       ├── betbot.db           # SQLite database
│       ├── chat.db             # Chat-historikk
│       └── features.csv        # Genererte features
├── models/
│   └── match_predictor.pkl     # Trent modell
├── src/
│   ├── data/
│   │   ├── footystats_client.py    # FootyStats API-klient
│   │   ├── norsk_tipping_client.py # Norsk Tipping API-klient
│   │   └── data_processor.py       # Data til SQLite
│   ├── features/
│   │   └── feature_engineering.py  # Feature-generering
│   ├── models/
│   │   └── match_predictor.py      # ML-modeller
│   ├── analysis/
│   │   └── value_finder.py         # Value bet detection
│   ├── predictions/
│   │   └── daily_picks.py          # DailyPicksFinder
│   ├── tui/
│   │   ├── app.py                  # BetBotApp chat-first layout
│   │   ├── commands.py             # /command parsing
│   │   ├── tasks.py                # Bakgrunnsjobber
│   │   ├── styles/app.tcss         # Layout CSS
│   │   └── widgets/                # ChatPanel, DataQualityPanel, ActivityPanel, EventLog
│   └── chat/
│       ├── llm_provider.py         # Provider-protokoll
│       ├── history.py              # Chat-historikk (SQLite)
│       ├── system_prompt.py        # Dynamisk systemprompt
│       └── providers/              # Anthropic og OpenAI
└── scripts/
    ├── test_api.py                 # Test API-tilkobling
    ├── download_all_leagues.py     # Last ned alle valgte ligaer
    ├── run_backtest.py             # Kjor backtest
    ├── get_todays_odds.py          # Hent odds fra Norsk Tipping
    └── run_tui.py                  # Start TUI dashboard
```

---

*Dokumentet sist oppdatert: Februar 2026*
