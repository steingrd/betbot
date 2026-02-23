---
title: "feat: Textual TUI Dashboard for BetBot"
type: feat
status: active
date: 2026-02-23
origin: docs/brainstorms/2026-02-23-tui-brainstorm.md
---

# feat: Textual TUI Dashboard for BetBot

## Overview

Bygge et Terminal User Interface (TUI) for BetBot med Textual-rammeverket. Multi-panel layout med statusbar, tabbete hovedpanel, hendelseslogg, ASCII fotball-spinner, og LLM-chat med streaming. Alle eksisterende `src/`-moduler gjenbrukes direkte - TUI-en er et tynt UI-lag over eksisterende forretningslogikk.

## Problem Statement / Motivation

I dag krever BetBot manuell kjoring av 3-5 scripts i sekvens (`download_all_leagues.py` -> `train_model.py` -> `daily_picks.py`). Det er ingen samlet oversikt over systemstatus, og resultater vises som ren konsoll-output. En TUI gir:

- Samlet operasjonell oversikt i ett vindu
- Ett-klikks kjoring av hele pipelinen
- LLM-analyse av predictions i naturlig sprak
- Persistent chat-historikk mellom sesjoner

## Proposed Solution

Textual-basert multi-panel app med folgende layout (se brainstorm: `docs/brainstorms/2026-02-23-tui-brainstorm.md`):

```
+------------------------------------------------------+
| Status: Data 2026-02-23 | Modell v12 | 1X2 acc: 55%  |
+-------------------------------------+--------+-------+
| [Predictions] [Data] [Trening]      | Hend-  | ,@,   |
|                                      | elses- | /`'\  |
|  Kamp          Marked  Edge  Konf   | logg   |  |    |
|  Arsenal-City  H       12%   Hoy    |        |(ASCII |
|  Liverpool-Utd BTTS    8%    Med    | 14:30  | fot-  |
|                                      |  Modell| ball) |
|                                      |  OK    |       |
+-------------------------------------+--------+-------+
| > Chat: Analyser dagens kamper...                    |
+------------------------------------------------------+
```

## Technical Approach

### Architecture

```
src/
  tui/
    app.py              # BetBotApp(App) - hovedapplikasjon
    widgets/
      status_bar.py     # StatusBar - reactive statuslinje
      football_spinner.py # FootballSpinner - ASCII-animasjon
      event_log.py      # EventLog(RichLog) - hendelseslogg
      chat_panel.py     # ChatPanel - input + markdown output
      predictions_tab.py # PredictionsTab - DataTable
      data_tab.py       # DataTab - nedlastingsstatus
      training_tab.py   # TrainingTab - modellytelse
    styles/
      app.tcss          # Textual CSS layout
    task_queue.py       # TaskQueue - serial oppgavekjoring
  chat/
    llm_provider.py     # LLMProvider Protocol + ChatMessage
    history.py          # ChatHistory - SQLite persistens
    system_prompt.py    # Kontekst-bygging for LLM
    providers/
      __init__.py       # create_provider() factory
      anthropic_provider.py
      openai_provider.py
```

TUI-en kaller eksisterende moduler direkte:
- `src.data.FootyStatsClient` + `DataProcessor` for nedlasting
- `src.features.FeatureEngineer` for feature-generering (med `progress_callback`)
- `src.models.MatchPredictor` for trening og prediksjon
- `src.analysis.ValueBetFinder` for value bets
- `scripts/daily_picks.py::DailyPicksFinder` for live predictions (flyttes til `src/`)

### Implementation Phases

#### Phase 1: Grunnleggende TUI-skjelett

Sett opp Textual-app med layout, navigering, tomme paneler, og grunnleggende livssyklus.

**Oppgaver:**
- Installer `textual` dependency i `requirements.txt`
- Opprett `src/tui/app.py` med `BetBotApp(App)`
- Implementer CSS-layout i `src/tui/styles/app.tcss` med dock-basert multi-panel
- Implementer `StatusBar` widget med reactive attributter (`data_date`, `model_version`, `accuracy`). Merk: brainstormen nevnte "ROI" men backtest-ROI krever separat kjoring av `run_backtest.py`. Bruker 1X2-accuracy fra treningsrapport i stedet, som alltid er tilgjengelig etter trening
- StatusBar leser initielle verdier fra DB/rapporter ved oppstart, viser "Ingen data | Ingen modell | --" nar ingenting finnes
- Implementer `EventLog(RichLog)` med fargekodede meldinger, max 500 linjer, auto-scroll, `HH:MM:SS` format
- Implementer `FootballSpinner` med ASCII-art animasjon i ovre hoyre hjorne
- Sett opp `TabbedContent` med tre tabs med tomme-tilstander: "Trykk Ctrl+D for aa laste ned data" etc.
- Implementer `Input` widget for chat nederst
- Definer keyboard bindings i `Footer`: `Ctrl+D` (data), `Ctrl+T` (tren), `Ctrl+P` (predictions), `Ctrl+Q` (avslutt)
- Graceful shutdown ved `Ctrl+Q`: avbryt aktive workers, lukk DB-connections
- Entry point: `scripts/run_tui.py`

**Filer:**
- `src/tui/__init__.py`
- `src/tui/app.py`
- `src/tui/styles/app.tcss`
- `src/tui/widgets/__init__.py`
- `src/tui/widgets/status_bar.py`
- `src/tui/widgets/event_log.py`
- `src/tui/widgets/football_spinner.py`
- `scripts/run_tui.py`

**Akseptkriterier:**
- [ ] App starter og viser alle paneler korrekt
- [ ] Tab-navigering mellom Predictions/Data/Trening fungerer
- [ ] Statusbar leser fra DB/rapporter ved oppstart, viser placeholders nar ingenting finnes
- [ ] Hendelseslogg viser "BetBot startet" ved oppstart
- [ ] Fotball-spinner animerer (men er inaktiv/skjult som default)
- [ ] Keyboard shortcuts vises i footer
- [ ] App haandterer terminal-resize uten aa krasje
- [ ] Minimum terminalstorrelse: 100x30 (vis melding hvis for liten)
- [ ] Graceful shutdown ved Ctrl+Q

#### Phase 2: Oppgavekjoring og datanedlasting

Implementer TaskQueue og datanedlasting-flow.

**Oppgaver:**
- Implementer `TaskQueue` klasse med: enqueue, current task, cancel, on_complete callback
- Maks 1 aktiv oppgave, FIFO-ko for ventende, dupliserte oppgaver avvises
- Implementer stdout-redirect context manager (`src/tui/stdout_capture.py`) som fanger `print()` fra eksisterende moduler og router til hendelsesloggen. Alle `@work(thread=True)` workers bruker denne.
- Aktiver SQLite WAL-modus ved oppstart for concurrent read/write mellom workers
- Integrer `FootyStatsClient` + `DataProcessor` for nedlasting via `@work(thread=True)`
- Logge per-sesong fremdrift til hendelseslogg: `"[3/30] Laster ned Premier League 2024/2025..."`
- Haandter feil: manglende API-nokkel, nettverksfeil, API rate-limiting
- Oppdater StatusBar med siste data-dato etter vellykket nedlasting
- Populer Data-tab med ligaoversikt og kampantall
- Implementer Escape for aa avbryte pagaende oppgave
- Spinner aktiveres under nedlasting, deaktiveres nar ferdig

**Filer:**
- `src/tui/task_queue.py`
- `src/tui/stdout_capture.py`
- `src/tui/widgets/data_tab.py`

**Akseptkriterier:**
- [ ] Ctrl+D starter nedlasting med spinner
- [ ] Fremdrift vises i hendelseslogg per sesong
- [ ] Feil logges med rod farge i hendelseslogg
- [ ] Manglende `FOOTYSTATS_API_KEY` gir tydelig feilmelding
- [ ] Ny oppgave legges i ko hvis en allerede kjorer
- [ ] Ko-oppgaver kjorer automatisk etter forrige er ferdig
- [ ] Escape avbryter pagaende oppgave
- [ ] Duplikat-oppgaver i ko avvises med melding
- [ ] Data-tab viser ligaoversikt med kampantall etter nedlasting
- [ ] StatusBar oppdateres med ny data-dato

#### Phase 3: Modeltrening

Implementer trenings-flow med progress og rapportering.

**Oppgaver:**
- Integrer `FeatureEngineer.generate_features(progress_callback=...)` via worker
- Integrer `MatchPredictor.train()` via stdout-capture (fra Phase 2) for treningsoutput
- Vise fremdrift i Training-tab: progress bar for feature-generering, steg-indikator for trening
- Lagre treningsrapport til `reports/latest_training_report.json`
- Oppdater StatusBar med ny modellversjon og accuracy
- Logge steg til hendelseslogg: "Feature-generering...", "Trener 1X2-modell...", "Modell lagret"
- Haandter utilstrekkelig data: "Trenger minst 100 kamper for trening"

**Filer:**
- `src/tui/widgets/training_tab.py`

**Akseptkriterier:**
- [ ] Ctrl+T starter trening via TaskQueue
- [ ] Progress bar i Training-tab under feature-generering
- [ ] Treningsrapport vises i Training-tab etter fullfort trening
- [ ] StatusBar viser ny modellversjon og accuracy
- [ ] Feilmelding ved utilstrekkelig data
- [ ] Treningsrapport lagres som JSON

#### Phase 4: Predictions

Implementer prediksjon-flow og predictions-tab.

**Oppgaver:**
- Flytt `DailyPicksFinder` fra `scripts/daily_picks.py` til `src/predictions/daily_picks.py`. Oppdater `scripts/daily_picks.py` til aa importere fra ny lokasjon (behold som CLI-wrapper)
- Integrer via worker: last modell -> hent NT-kamper -> beregn features -> prediker -> finn value bets
- Populer Predictions-tab DataTable med kolonner: Tid, Kamp, Liga, Marked, Edge, Konfidanse
- Sortert etter edge (synkende) som default
- Haandter tomme resultater: "Ingen value bets funnet for i dag"
- Haandter ingen kamper: "Ingen kamper tilgjengelig fra Norsk Tipping"
- Haandter manglende modell: "Ingen modell funnet. Tren forst (Ctrl+T)"
- Vis stale-data advarsel hvis data er eldre enn 7 dager
- Automatisk utlos predictions etter vellykket trening (med banner i tab)
- Manuell trigger via Ctrl+P

**Filer:**
- `src/predictions/__init__.py`
- `src/predictions/daily_picks.py` (flyttet fra scripts/)
- `src/tui/widgets/predictions_tab.py`

**Akseptkriterier:**
- [ ] Ctrl+P starter prediksjon via TaskQueue
- [ ] Predictions-tab viser value bets i DataTable
- [ ] Tomme-tilstand haandteres med tydelige meldinger
- [ ] Stale-data advarsel vises hvis data > 7 dager gammel
- [ ] Auto-trigger etter trening med "Modell oppdatert"-banner
- [ ] Manglende modell gir tydelig feilmelding

#### Phase 5: LLM-integrasjon

Implementer chat med konfigurerbar LLM-provider og streaming.

**Oppgaver:**
- Implementer `LLMProvider` Protocol i `src/chat/llm_provider.py`
- Implementer `AnthropicProvider` med `AsyncAnthropic` streaming
- Implementer `OpenAIProvider` med `AsyncOpenAI` streaming
- Implementer `create_provider()` factory - velger basert paa tilgjengelige API-nokler i `.env`
- Implementer `ChatHistory` med SQLite-persistens i `data/processed/chat.db`
- Implementer `system_prompt.py` med kontekst-bygging: predictions + treningsrapport + data-stats
- Implementer `ChatPanel` widget med Markdown-rendering og streaming
- Auto-analyse: nar nye predictions er klare, trigger LLM-oppsummering
- Fri chat: bruker skriver sporsmal, LLM svarer med full kontekst
- Token-haandtering: siste 20 meldinger i kontekst, alle lagret i SQLite
- `/clear` kommando for aa nullstille chat
- Input deaktivert mens LLM streamer. Ny melding koes ikke.
- Haandter manglende API-nokkel: "Sett ANTHROPIC_API_KEY eller OPENAI_API_KEY i .env"
- Haandter streaming-feil: vis feilmelding i chat, behold partial response
- Chat tilgjengelig uavhengig av TaskQueue (LLM-kall er separate)

**Filer:**
- `src/chat/__init__.py`
- `src/chat/llm_provider.py`
- `src/chat/history.py`
- `src/chat/system_prompt.py`
- `src/chat/providers/__init__.py`
- `src/chat/providers/anthropic_provider.py`
- `src/chat/providers/openai_provider.py`
- `src/tui/widgets/chat_panel.py`

**Akseptkriterier:**
- [ ] LLM-provider velges automatisk basert paa tilgjengelige API-nokler
- [ ] Chat-input sender melding til LLM med streaming-respons
- [ ] Respons renderes som Markdown i chat-panelet
- [ ] Auto-analyse kjorer etter nye predictions
- [ ] Chat-historikk lagres i SQLite mellom sesjoner
- [ ] `/clear` nullstiller chat
- [ ] Manglende API-nokkel gir tydelig feilmelding (ikke krasj)
- [ ] Nettverksfeil under streaming viser feilmelding og beholder partial response
- [ ] Chat fungerer mens andre oppgaver kjorer

#### Phase 6: Ende-til-ende testing og polish

Verifiser hele pipelinen og finjuster helhetsopplevelsen.

**Oppgaver:**
- Test full pipeline: oppstart -> nedlasting -> trening -> predictions -> LLM-analyse
- Test forste-gangs brukeropplevelse (ingen data, ingen modell, ingen API-nokler)
- Test feilscenarier: nettverksfeil, manglende nokler, utilstrekkelig data
- Test oppgaveko: start oppgave mens en kjorer, avbryt med Escape
- Oppdater `requirements.txt` med alle nye dependencies
- Oppdater `CLAUDE.md` med TUI-dokumentasjon (entry point, shortcuts)

**Akseptkriterier:**
- [ ] Full pipeline fungerer fra forste kjoring uten feil
- [ ] Alle feilscenarier gir tydelige meldinger (ikke stack traces)
- [ ] Ko-system fungerer korrekt med 2+ oppgaver

## Dependencies

### Nye Python-pakker

```
textual>=1.0.0          # TUI-rammeverk
anthropic>=0.40.0        # Claude API (valgfri)
openai>=1.50.0           # OpenAI API (valgfri)
```

### Eksisterende moduler som gjenbrukes

| Modul | Brukes i Phase |
|---|---|
| `src.data.FootyStatsClient` | 2 |
| `src.data.DataProcessor` | 2, 3, 4 |
| `src.features.FeatureEngineer` | 3, 4 |
| `src.models.MatchPredictor` | 3, 4 |
| `src.analysis.ValueBetFinder` | 4 |
| `src.data.NorskTippingClient` | 4 |

### Modul som flyttes

`scripts/daily_picks.py::DailyPicksFinder` -> `src/predictions/daily_picks.py`

## Keyboard Shortcuts

| Snarvei | Handling | Tilgjengelig |
|---|---|---|
| `Ctrl+D` | Last ned data | Alltid (kolegges hvis opptatt) |
| `Ctrl+T` | Tren modell | Alltid (kolegges hvis opptatt) |
| `Ctrl+P` | Kjor predictions | Alltid (kolegges hvis opptatt) |
| `Escape` | Avbryt pagaende oppgave | Kun under aktiv oppgave |
| `Tab` | Bytt tab i hovedpanel | Alltid |
| `Ctrl+Q` | Avslutt | Alltid |

Alle shortcuts vises i Textual Footer-widget.

## Feilhaandtering

| Scenario | Haandtering |
|---|---|
| Manglende `FOOTYSTATS_API_KEY` | Feilmelding i hendelseslogg + Data-tab |
| Manglende LLM API-nokkel | Chat viser "Sett API-nokkel i .env", resten fungerer |
| Nettverksfeil under nedlasting | Logg feil, partial data beholdes, spinner stopper |
| Nettverksfeil under LLM-streaming | Vis partial respons + feilmelding |
| Utilstrekkelig data for trening | Feilmelding: "Trenger minst 100 kamper" |
| Ingen kamper fra Norsk Tipping | Melding i Predictions-tab |
| Ingen value bets funnet | Melding i Predictions-tab |
| Worker-exception | Logg til hendelseslogg (rod), stopp spinner, avancer ko |
| Database locked | SQLite WAL-modus forhindrer dette |
| Terminal for liten | Overlay-melding: "Terminal for liten (min 100x30)" |

## Spraak

Norsk UI konsistent med eksisterende output. Unntak:
- Tekniske termer beholdes paa engelsk der norsk er unaturlig: "BTTS", "Over 2.5", "edge"
- Modellnavn og API-termer paa engelsk
- Lagnavn og liganavn som fra kilde (engelsk fra FootyStats, norsk fra Norsk Tipping)

## Sources & References

### Origin

- **Brainstorm:** [docs/brainstorms/2026-02-23-tui-brainstorm.md](docs/brainstorms/2026-02-23-tui-brainstorm.md) - Beslutninger: Multi-panel layout, Textual rammeverk, ekte LLM med konfigurerbar provider, ko-system, norsk UI, persistent chat

### Internal References

- `src/data/footystats_client.py` - API-klient med caching
- `src/data/data_processor.py` - SQLite database-operasjoner
- `src/features/feature_engineering.py:283` - `progress_callback` parameter
- `src/models/match_predictor.py` - XGBoost trening/prediksjon
- `src/analysis/value_finder.py` - Value bet-kalkulasjon
- `scripts/daily_picks.py` - DailyPicksFinder orchestrator (flyttes til src/)
- `scripts/train_model.py` - Treningslogikk som referanse

### External References

- [Textual Documentation](https://textual.textualize.io/) - TUI-rammeverk
- [Textual Workers Guide](https://textual.textualize.io/guide/workers/) - Background task execution
- [Textual CSS Guide](https://textual.textualize.io/guide/CSS/) - Layout og styling
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) - Claude streaming API
- [OpenAI Python SDK](https://github.com/openai/openai-python) - OpenAI streaming API
