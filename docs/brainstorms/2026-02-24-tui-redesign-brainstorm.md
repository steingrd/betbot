---
date: 2026-02-24
topic: tui-redesign
---

# TUI Redesign: Chat-first Dashboard

## What We're Building

A complete redesign of the BetBot TUI from a tab-based dashboard to a chat-first single-screen layout. The chat becomes the command center — all actions are triggered via `/commands`, and results (predictions, training reports) render inline in the conversation. Three right-side panels provide persistent visibility into data quality, current activity, and event history.

## Why This Approach

The current tab-based design hides important information behind tabs. Users can't see what's running, what data they have, or what the current model status is without switching tabs. The "Data" and "Trening" tabs are confusing and rarely useful on their own. By making the chat the primary interface and keeping status always visible, the TUI becomes both simpler and more informative.

### Approaches Considered

1. **Improved tabs** — Keep tabs but add better status indicators. Rejected: doesn't solve the fundamental "hidden info" problem.
2. **Dashboard + chat** — Split-screen with a data dashboard on one side. Rejected: too much visual noise, predictions/reports are better consumed in conversation context.
3. **Chat-first with side panels** — (Chosen) Chat dominates, side panels show status, results flow inline. Clean, focused, always-visible status.

## Key Decisions

- **No tabs**: Single-screen layout replaces TabbedContent with 3 tabs
- **Chat commands**: `/download`, `/train`, `/predict`, `/help`, `/clear` replace Ctrl+D/T/P
- **Inline results**: Predictions table and training reports render in chat conversation
- **Three right panels**: Data quality (top), Activity with spinner (middle), Event log (bottom)
- **Welcome message**: On startup, auto-detect data/model and post status summary
- **Minimal keybindings**: Only Ctrl+Q (quit) and Escape (cancel running task)

## Layout

```
+-----------------------------------+------------------+
|                                   | Datakvalitet     |
|                                   | Siste data: ...  |
|                                   | Ligaer: 8        |
|  Chat-dialog                      | Modell: v12      |
|  (historikk + inline resultater)  | Accuracy: 73%    |
|                                   +------------------+
|  > /predict                       | Aktivitet        |
|  Fant 3 value bets:               | (spinner + hva   |
|  +-------+----------+------+     |  som kjorer)     |
|  | Tid   | Kamp     | Edge |     +------------------+
|  | 15:00 | LIV-ARS  | +12% |     |                  |
|  +-------+----------+------+     |  Event log       |
|                                   |  14:02 Lastet PL |
|  Basert paa analysen ser vi...    |  14:03 Trent ok  |
|                                   |  14:04 3 picks   |
+-----------------------------------+------------------+
| > Skriv melding eller /kommando...                    |
+-------------------------------------------------------+
```

## What Changes

### Removed
- TabbedContent with 3 tabs (Predictions, Data, Trening)
- StatusBar widget (1-line top bar)
- PredictionsView widget (standalone predictions table)
- TrainingView widget (progress bar + report view)
- DataTableView widget (league data summary)
- Ctrl+D/T/P keybindings for actions

### Kept/Improved
- ChatPanel — expanded to support /commands and inline table rendering
- EventLog — kept as-is in right panel
- FootballSpinner — moved into Activity panel
- Chat providers (Anthropic/OpenAI) and streaming
- Background task architecture (workers + messages)
- Chat history (SQLite persistence)

### New
- DataQualityPanel — persistent display of data/model key metrics
- ActivityPanel — spinner + description of current running task
- Command parsing in chat input (/download, /train, /predict, /help, /clear)
- Inline table rendering in chat messages (predictions, reports)
- Welcome message with auto-detected status on startup

## Open Questions

- Exact proportions for right panels (fixed height vs. flexible)
- Whether /download should show per-league progress inline in chat or only in event log
- How to handle very large prediction tables inline (scrollable region?)

## Next Steps

-> Plan implementation phases and create beads issues
