# BetBot TUI - Brainstorm

**Dato:** 2026-02-23
**Status:** Brainstorm

## Hva vi bygger

Et Terminal User Interface (TUI) for BetBot som gir en komplett operasjonell oversikt over ML-basert value bet-analyse. Bygget med Textual (Python TUI-rammeverk) med multi-panel layout der alt er synlig samtidig.

Inkluderer ekte LLM-integrasjon (konfigurerbar provider, starter med Claude) som automatisk analyserer predictions og lar brukeren stille oppfolgingssporsmal i fri chat.

## Hvorfor denne tilnaermingen

**Multi-panel (Tilnarming A)** ble valgt over tab-basert og chat-first fordi:
- Alt synlig samtidig gir best operasjonell oversikt
- Naturlig for et monitoring/analyse-verktoy
- Statusbar, hendelseslogg, og hovedinnhold lever side om side
- Tab-navigering innenfor hovedpanelet gir fremdeles fokusert innhold

**Chat-first (Tilnarming C)** ble vurdert men forkastet - predictions og tabeller fortjener strukturert visning, ikke inline i en chat-strom.

## Layout

```
+------------------------------------------------------+
| Status: Data 2026-02-23 | Modell v12 | ROI +8.2%    |
+-------------------------------------+--------+-------+
| [Predictions] [Data] [Trening]      | Hend-  | ,@,   |
|                                      | elses- | /`'\  |
|  Kamp          Marked  Edge  Konf   | logg   |  |    |
|  Arsenal-City  H       12%   Hoy    |        |(ASCII |
|  Liverpool-Utd BTTS    8%    Med    | 14:30  | fot-  |
|                                      |  Modell| ball) |
|                                      |  OK    |       |
|                                      | 14:25  |       |
|                                      |  Data  |       |
+-------------------------------------+--------+-------+
| > Chat: Analyser dagens kamper...                    |
+------------------------------------------------------+
```

### Paneler

1. **Statusbar (topp)** - Siste data-dato, modellversjon, backtest-ROI, aktiv oppgave
2. **Hovedpanel (midten-venstre)** - Tab-navigering mellom:
   - **Predictions** - Value bets-tabell med edge, konfidanse, marked
   - **Data** - Nedlastingsstatus, liga-oversikt, antall kamper
   - **Trening** - Modellytelse, treningsrapport, progress
3. **Hendelseslogg (midten-hoyre)** - Kronologisk logg over alt som har skjedd
4. **Fotball-spinner (ovre hoyre hjorne)** - ASCII-art fotball som spinner nar oppgaver kjorer
5. **Chat-input (bunn)** - LLM-chat for analyse og sporsmol

### Navigering

- **Tab** - Bytt mellom tabs i hovedpanelet (Predictions/Data/Trening)
- **Hurtigtaster** for vanlige handlinger (f.eks. Ctrl+D = last ned data, Ctrl+T = tren modell)
- Chat-input fokusert som default (ala Claude Code)

## Kjernefunksjoner

### 1. Datanedlasting
- Trigger via hurtigtast eller chat-kommando
- Viser progress i hovedpanelet + spinner aktiveres
- Hendelseslogg oppdateres fortlopende
- Bruker eksisterende `FootyStatsClient` og `DataProcessor` fra `src/`

### 2. Modeltrening
- Trigger via hurtigtast eller chat-kommando
- Viser treningsprogress (utnytter eksisterende `progress_callback` i FeatureEngineer)
- Oppdaterer statusbar med ny modellversjon nar ferdig

### 3. Bet Predictions
- Kjorer automatisk etter trening, eller manuelt
- Viser value bets i predictions-tab
- LLM analyserer automatisk og presenterer oppsummering i chatten

### 4. LLM-chat
- Automatisk analyse nar nye predictions er klare
- Fri chat for oppfolgingssporsmal ("Forklar hvorfor Arsenal er value")
- Konfigurerbar provider (Claude API forst, OpenAI-kompatibel som alternativ)
- API-nokkel via `.env`

### 5. Hendelseslogg
- Alt som skjer logges med tidsstempel
- Scroll-bar hendelseslogg i eget panel
- Fargekodet etter type (info, suksess, feil, advarsel)

## Oppgavekjoring

- **Kun en langvarig oppgave om gangen** (nedlasting ELLER trening)
- **Ko-system**: Hvis bruker starter ny oppgave mens en pagar, legges den i ko
- Ko vises i hendelsesloggen
- Fotball-spinner er aktiv sa lenge en oppgave kjorer

## Tekniske beslutninger

| Beslutning | Valg | Begrunnelse |
|---|---|---|
| TUI-rammeverk | Textual | Modent, CSS-styling, widgets, asynk-stotte |
| LLM-integrasjon | Ekte, konfigurerbar | Claude API forst, enkel a bytte provider |
| Chat-modus | Auto-analyse + fri chat | Beste av begge verdener |
| Layout | Multi-panel | Alt synlig samtidig, best for monitoring |
| Oppgavehandtering | Ko-system | Bruker slipper a vente for a starte neste oppgave |
| Sprak | Norsk | Konsistent med eksisterende output |

## Arkitekturhensyn

- All forretningslogikk bor allerede i `src/` - TUI-en er et tynt UI-lag
- Scripts kan gjenbrukes som referanse, men TUI kaller `src/`-moduler direkte
- Asynk-kjoring av langvarige oppgaver via Textual workers
- LLM-klient som eget modul i `src/` med provider-abstraksjon

## Avklarte sporsmal

1. **LLM-kontekst**: Alt tilgjengelig - predictions + treningsrapport + backtest-ROI + ligastatistikk. Gir best mulig analyse.
2. **Persistens**: Ja, chat-historikk lagres mellom sesjoner. Brukeren kan referere til tidligere analyser.
3. **Konfigurasjon**: Nei, hardkodet. Holder det enkelt - kan alltid legge til config-fil senere.
