# FootyStats API Data Analysis

Generert: 2026-02-05

## Oversikt

Denne rapporten analyserer hvilke data som er tilgjengelig fra FootyStats API og hvordan vi kan utnytte dem bedre i BetBot.

| Kategori | Antall |
|----------|--------|
| **Totalt antall API-felter** | 215 |
| **Felter vi bruker i dag** | 43 (20%) |
| **Ubrukte felter** | 172 (80%) |

---

## 1. Felter Vi Bruker I Dag

### Match-identifikasjon
- `id`, `season`, `game_week`, `date_unix`

### Lag
- `homeID`, `home_name`, `awayID`, `away_name`

### Resultat
- `homeGoalCount`, `awayGoalCount`, `totalGoalCount`

### Grunnleggende statistikk
- Skudd: `team_a_shots`, `team_b_shots`, `team_a_shotsOnTarget`, `team_b_shotsOnTarget`
- Ballbesittelse: `team_a_possession`, `team_b_possession`
- Cornere: `team_a_corners`, `team_b_corners`
- Frispark: `team_a_fouls`, `team_b_fouls`
- Kort: `team_a_yellow_cards`, `team_b_yellow_cards`, `team_a_red_cards`, `team_b_red_cards`

### xG
- `team_a_xg`, `team_b_xg`

### Halvtid
- `ht_goals_team_a`, `ht_goals_team_b`

### Odds (1X2)
- `odds_ft_1`, `odds_ft_x`, `odds_ft_2`

### Odds (Over/Under)
- `odds_ft_over25`, `odds_ft_under25`, `odds_ft_over15`, `odds_ft_under15`

### Odds (BTTS)
- `odds_btts_yes`, `odds_btts_no`

### Beregnet
- `btts`, `over25`, `over15`, `home_ppg`, `away_ppg`

---

## 2. Ubrukte Felter - Kategorisert

### 2.1 PRE-MATCH DATA (Mest verdifull for prediksjon!)

Disse feltene inneholder **pre-match data** som er ekstremt verdifulle for prediksjon:

| Felt | Beskrivelse | Dekning | Gjennomsnitt |
|------|-------------|---------|--------------|
| `pre_match_home_ppg` | Hjemmelagets PPG **FØR** kampen | 100% | 1.48 |
| `pre_match_away_ppg` | Bortelagets PPG **FØR** kampen | 100% | 1.17 |
| `pre_match_teamA_overall_ppg` | Hjemmelagets overall PPG pre-match | 100% | 1.36 |
| `pre_match_teamB_overall_ppg` | Bortelagets overall PPG pre-match | 100% | 1.37 |
| `team_a_xg_prematch` | Forventet xG for hjemmelaget pre-match | 100% | 1.45 |
| `team_b_xg_prematch` | Forventet xG for bortelaget pre-match | 100% | 1.22 |
| `total_xg_prematch` | Total forventet xG pre-match | 100% | 2.67 |

**KRITISK INNSIKT:** Vi bruker `home_ppg` og `away_ppg` i dag, men disse kan potensielt inkludere kampen selv (leakage). `pre_match_*` feltene er garantert pre-match og bor brukes i stedet!

### 2.2 ANGREPSSTATISTIKK

| Felt | Beskrivelse | Dekning | Gjennomsnitt |
|------|-------------|---------|--------------|
| `team_a_attacks` | Antall angrep hjemmelag | 100% | 116 |
| `team_b_attacks` | Antall angrep bortelag | 100% | 107 |
| `team_a_dangerous_attacks` | Farlige angrep hjemmelag | 100% | 56 |
| `team_b_dangerous_attacks` | Farlige angrep bortelag | 100% | 46 |

**Verdi:** Ratio mellom farlige angrep og totale angrep kan indikere angrepskvalitet.

### 2.3 DETALJERT MÅLSTATISTIKK

| Felt | Beskrivelse | Dekning | Gjennomsnitt |
|------|-------------|---------|--------------|
| `team_a_0_10_min_goals` | Mål 0-10 min hjemmelag | 100% | 0.12 |
| `team_b_0_10_min_goals` | Mål 0-10 min bortelag | 100% | 0.09 |
| `goals_2hg_team_a` | 2. omgangsmål hjemmelag | 100% | 0.89 |
| `goals_2hg_team_b` | 2. omgangsmål bortelag | 100% | 0.68 |
| `team_a_penalty_goals` | Straffemål hjemmelag | 100% | 0.11 |
| `team_b_penalty_goals` | Straffemål bortelag | 100% | 0.11 |
| `homeGoals_timings` | Liste med målminutter hjemme | 100% | - |
| `awayGoals_timings` | Liste med målminutter borte | 100% | - |

**Verdi:** Kan bygge features for tidlig-mål-sannsynlighet og andre-omgang-mål.

### 2.4 DETALJERT SKUDDSTATISTIKK

| Felt | Beskrivelse | Dekning | Gjennomsnitt |
|------|-------------|---------|--------------|
| `team_a_shotsOffTarget` | Skudd utenfor hjemme | 100% | 5.57 |
| `team_b_shotsOffTarget` | Skudd utenfor borte | 100% | 4.31 |

**Verdi:** Ratio skudd-på-mål vs totale skudd indikerer finishing-kvalitet.

### 2.5 DETALJERT CORNER-STATISTIKK

| Felt | Beskrivelse | Dekning | Gjennomsnitt |
|------|-------------|---------|--------------|
| `totalCornerCount` | Total cornere i kampen | 100% | - |
| `corner_fh_count` | Cornere i 1. omgang | 100% | 4.81 |
| `corner_2h_count` | Cornere i 2. omgang | 100% | 5.47 |
| `team_a_fh_corners` | Hjemmelag cornere 1. omgang | 100% | 2.72 |
| `team_b_fh_corners` | Bortelag cornere 1. omgang | 100% | 2.09 |
| `team_a_2h_corners` | Hjemmelag cornere 2. omgang | 100% | - |
| `team_b_2h_corners` | Bortelag cornere 2. omgang | 100% | - |

### 2.6 DETALJERT KORTSTATISTIKK

| Felt | Beskrivelse | Dekning |
|------|-------------|---------|
| `team_a_cards_num` | Totale kort hjemmelag | 100% |
| `team_b_cards_num` | Totale kort bortelag | 100% |
| `team_a_fh_cards` | Kort 1. omgang hjemme | 100% |
| `team_b_fh_cards` | Kort 1. omgang borte | 100% |
| `team_a_2h_cards` | Kort 2. omgang hjemme | 100% |
| `team_b_2h_cards` | Kort 2. omgang borte | 100% |
| `total_fh_cards` | Totale kort 1. omgang | 100% |
| `total_2h_cards` | Totale kort 2. omgang | 100% |

### 2.7 ANDRE STATISTIKKER

| Felt | Beskrivelse | Dekning | Gjennomsnitt |
|------|-------------|---------|--------------|
| `team_a_offsides` | Offside hjemmelag | 100% | 2.23 |
| `team_b_offsides` | Offside bortelag | 100% | 1.89 |
| `team_a_freekicks` | Frispark hjemmelag | 100% | - |
| `team_b_freekicks` | Frispark bortelag | 100% | - |
| `team_a_throwins` | Innkast hjemmelag | 100% | - |
| `team_b_throwins` | Innkast bortelag | 100% | - |
| `team_a_goalkicks` | Utspark hjemmelag | 100% | - |
| `team_b_goalkicks` | Utspark bortelag | 100% | - |

### 2.8 METADATA MED PREDIKTIV VERDI

| Felt | Beskrivelse | Dekning | Gjennomsnitt |
|------|-------------|---------|--------------|
| `attendance` | Oppmøte | 100% | 38,187 |
| `refereeID` | Dommer-ID | 100% | - |
| `coach_a_ID` | Trener hjemmelag | 100% | - |
| `coach_b_ID` | Trener bortelag | 100% | - |
| `stadium_name` | Stadion | 100% | - |

**Verdi:** Dommer-analyse (kort-tendenser), trener-analyse (taktikk), hjemmebane-fordel.

### 2.9 POTENSIAL/SANNSYNLIGHETS-FELTER

FootyStats har egne beregnede sannsynligheter:

| Felt | Beskrivelse | Dekning | Gjennomsnitt |
|------|-------------|---------|--------------|
| `btts_potential` | BTTS-sannsynlighet (0-100) | 100% | 50.4% |
| `o25_potential` | Over 2.5 sannsynlighet | 100% | 53.4% |
| `o35_potential` | Over 3.5 sannsynlighet | 100% | 30.0% |
| `corners_potential` | Corner-potensial | 100% | 9.6 |

**Verdi:** Kan brukes som benchmark eller ensemble-feature.

### 2.10 ODDS - NYE MARKEDER

#### Halvtid 1X2
| Felt | Dekning | Gjennomsnitt |
|------|---------|--------------|
| `odds_1st_half_result_1` | 100% | 3.37 |
| `odds_1st_half_result_x` | 100% | 2.34 |
| `odds_1st_half_result_2` | 100% | 4.75 |

#### 2. omgang 1X2
| Felt | Dekning | Gjennomsnitt |
|------|---------|--------------|
| `odds_2nd_half_result_1` | 100% | 3.00 |
| `odds_2nd_half_result_x` | 100% | 2.73 |
| `odds_2nd_half_result_2` | 100% | 4.25 |

#### Double Chance
| Felt | Dekning | Gjennomsnitt |
|------|---------|--------------|
| `odds_doublechance_1x` | 100% | 1.58 |
| `odds_doublechance_12` | 100% | 1.24 |
| `odds_doublechance_x2` | 100% | 2.15 |

#### Clean Sheet
| Felt | Dekning | Gjennomsnitt |
|------|---------|--------------|
| `odds_team_a_cs_yes` | 100% | 3.65 |
| `odds_team_b_cs_yes` | 100% | 5.54 |

#### Win to Nil
| Felt | Dekning | Gjennomsnitt |
|------|---------|--------------|
| `odds_win_to_nil_1` | 100% | 5.32 |
| `odds_win_to_nil_2` | 100% | 8.60 |

#### Team to Score First
| Felt | Dekning | Gjennomsnitt |
|------|---------|--------------|
| `odds_team_to_score_first_1` | 100% | 2.02 |
| `odds_team_to_score_first_2` | 100% | 2.62 |
| `odds_team_to_score_first_x` | 100% | 12.51 |

#### Over/Under 3.5+ og 4.5+
| Felt | Dekning | Gjennomsnitt |
|------|---------|--------------|
| `odds_ft_over35` | 100% | 3.10 |
| `odds_ft_over45` | 100% | 5.90 |

#### Corner odds
| Felt | Dekning | Gjennomsnitt |
|------|---------|--------------|
| `odds_corners_1` | 100% | 2.06 |
| `odds_corners_2` | 100% | 3.40 |
| `odds_corners_over_105` | 100% | 1.74 |

---

## 3. Anbefalte Nye Features

### Prioritet 1: KRITISK (Implementer umiddelbart)

#### 1.1 Bytt til pre-match PPG
```python
# Erstatt
"home_ppg": m.get("home_ppg"),
"away_ppg": m.get("away_ppg"),

# Med
"home_ppg": m.get("pre_match_home_ppg"),
"away_ppg": m.get("pre_match_away_ppg"),
"home_overall_ppg": m.get("pre_match_teamA_overall_ppg"),
"away_overall_ppg": m.get("pre_match_teamB_overall_ppg"),
```
**Begrunnelse:** Unngår potensiell data leakage. Kritisk for modell-integritet.

#### 1.2 Pre-match xG
```python
"home_xg_prematch": m.get("team_a_xg_prematch"),
"away_xg_prematch": m.get("team_b_xg_prematch"),
"total_xg_prematch": m.get("total_xg_prematch"),
```
**Begrunnelse:** Forventet mål basert på historikk - sterk prediktor for over/under.

### Prioritet 2: HØY (Stor prediktiv verdi)

#### 2.1 Angrepskvalitet
```python
# Nye kolonner
"home_attacks": m.get("team_a_attacks"),
"away_attacks": m.get("team_b_attacks"),
"home_dangerous_attacks": m.get("team_a_dangerous_attacks"),
"away_dangerous_attacks": m.get("team_b_dangerous_attacks"),

# Beregnet feature
"home_attack_quality": dangerous_attacks / attacks,  # Ratio
"away_attack_quality": dangerous_attacks / attacks,
```
**Begrunnelse:** Kvaliteten på angrep korrelerer sterkt med målsjanser.

#### 2.2 Skuddefektivitet
```python
"home_shots_off_target": m.get("team_a_shotsOffTarget"),
"away_shots_off_target": m.get("team_b_shotsOffTarget"),

# Feature
"home_shot_accuracy": shots_on_target / total_shots,
"away_shot_accuracy": shots_on_target / total_shots,
```

#### 2.3 FootyStats potensial som feature
```python
"fs_btts_potential": m.get("btts_potential"),
"fs_o25_potential": m.get("o25_potential"),
"fs_o35_potential": m.get("o35_potential"),
```
**Begrunnelse:** Ekstern modell som ensemble-input.

### Prioritet 3: MEDIUM (Spesialiserte markeder)

#### 3.1 Tidlige mål
```python
"home_early_goals": m.get("team_a_0_10_min_goals"),
"away_early_goals": m.get("team_b_0_10_min_goals"),
```
**Use case:** Predikere "mål i første 10 min" eller "team to score first".

#### 3.2 Andre-omgang-mål
```python
"home_2h_goals": m.get("goals_2hg_team_a"),
"away_2h_goals": m.get("goals_2hg_team_b"),
```
**Use case:** 2. omgang over/under markeder.

#### 3.3 Detaljert corner-data
```python
"total_corners": m.get("totalCornerCount"),
"corners_1h": m.get("corner_fh_count"),
"corners_2h": m.get("corner_2h_count"),
"home_corners_1h": m.get("team_a_fh_corners"),
```
**Use case:** Corner-betting markeder.

### Prioritet 4: LAV (Nyttig men kompleks)

#### 4.1 Dommer-analyse
```python
"referee_id": m.get("refereeID"),
```
Krever egen tabell for dommer-statistikk (kort-snitt, straffe-tendenser).

#### 4.2 Trener-analyse
```python
"home_coach_id": m.get("coach_a_ID"),
"away_coach_id": m.get("coach_b_ID"),
```
Krever egen tabell for trener-statistikk.

#### 4.3 Oppmøte/Atmosfære
```python
"attendance": m.get("attendance"),
```
Kan normaliseres mot stadionkapasitet for hjemmebane-fordel-analyse.

---

## 4. Nye Betting-markeder Vi Kan Støtte

Med de nye dataene kan vi predikere:

| Marked | Relevante felter | Kompleksitet |
|--------|------------------|--------------|
| **Halvtid 1X2** | `ht_goals_*`, `odds_1st_half_*` | Lav |
| **2. omgang Over/Under** | `goals_2hg_*`, `odds_2nd_half_*` | Lav |
| **Team to Score First** | `*_0_10_min_goals`, `odds_team_to_score_first_*` | Medium |
| **Clean Sheet** | `*_cs_yes/no`, xG-data | Medium |
| **Win to Nil** | Kombinasjon av CS + 1X2 | Medium |
| **Total Corners** | Corner-statistikk, `odds_corners_*` | Medium |
| **Double Chance** | Eksisterende 1X2-modell + `odds_doublechance_*` | Lav |

---

## 5. Implementasjonsplan

### Fase 1: Quick Wins (1-2 dager)
1. Bytt til `pre_match_*` PPG-felter
2. Legg til `*_xg_prematch`
3. Legg til FootyStats `*_potential` som features
4. Legg til `odds_ft_over35`, `odds_ft_over45`

### Fase 2: Nye Features (3-5 dager)
1. Angrepskvalitet-ratio
2. Skuddefektivitet
3. Tidlige mål og 2. omgangs-mål
4. Detaljert corner-data

### Fase 3: Nye Markeder (1-2 uker)
1. Halvtid-prediksjon
2. Clean sheet prediksjon
3. Corner-prediksjon

### Fase 4: Avansert (Fremtidig)
1. Dommer-analyse
2. Trener-analyse
3. Oppmøte-faktor

---

## 6. Konklusjon

Vi bruker kun **20%** av tilgjengelig data fra FootyStats API. De viktigste funnene:

1. **Kritisk:** Vi bør bruke `pre_match_*` feltene i stedet for post-match PPG for å unnga data leakage.

2. **Høy verdi:** Pre-match xG, angrepskvalitet, og FootyStats sine egne potensial-beregninger bør legges til umiddelbart.

3. **Nye markeder:** Vi har data til å støtte halvtid-betting, clean sheet, og corner-markeder.

4. **100% datakvalitet:** Alle analyserte felter har 100% dekning i Premier League-dataene.

Implementering av Fase 1 alene vil sannsynligvis gi merkbar forbedring i prediksjonskvalitet.
