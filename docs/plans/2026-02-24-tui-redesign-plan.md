---
date: 2026-02-24
topic: tui-redesign
brainstorm: ../brainstorms/2026-02-24-tui-redesign-brainstorm.md
---

# TUI Redesign: Implementation Plan

## Overview

Transform BetBot TUI from a tab-based dashboard to a chat-first single-screen layout.

**Current**: `StatusBar` (top) -> `Horizontal[TabbedContent[Predictions, Data, Trening], Vertical[EventLog, Spinner]]` (middle) -> `ChatPanel` (bottom, 12 lines) -> `Footer`

**Target**: `Horizontal[ChatPanel (expanded), Vertical[DataQualityPanel, ActivityPanel, EventLog]]` -> `Footer`

## Dependency Graph

```
Phase 1 (New widgets) ──────┐
                              ├── Phase 3 (Layout switch) ── Phase 4 (Inline results) ── Phase 5 (Welcome) ── Phase 6 (Cleanup)
Phase 2 (Command parser) ───┘
```

Phases 1 and 2 can be developed in parallel. Phase 3 depends on both. Phases 4-6 are sequential.

---

## Phase 1: New Right-Side Panels (DataQualityPanel + ActivityPanel)

Create the two new widgets without changing the existing layout.

### Files created
- `src/tui/widgets/data_quality_panel.py`
- `src/tui/widgets/activity_panel.py`

### DataQualityPanel

Widget displaying key metrics in a compact vertical list:
- Siste data: YYYY-MM-DD
- Ligaer: N
- Kamper: N
- Modell: vXXXXXXXX
- 1X2 acc: XX.X%
- Over 2.5: XX.X%
- BTTS: XX.X%

Reuse data-loading logic from `StatusBar._load_initial_values()` and `DataTableView.refresh_data()`. Query SQLite DB for match/league counts, read training report JSON for model info. Public `refresh()` method for app to call after downloads/training.

### ActivityPanel

Widget showing current running task:
- Contains a `FootballSpinner` (reuse existing widget) + `Static` label
- `set_task(description: str)` / `clear_task()` methods
- When active: spinner animating + description text
- When idle: dim "Ingen aktiv oppgave", spinner stopped

### Verification
- Mount widgets in isolation to verify data display
- Verify DataQualityPanel reads correct metrics from DB
- Verify ActivityPanel spinner + label toggle

---

## Phase 2: Command Parser and Chat Command Infrastructure

Build `/command` parsing so chat input can dispatch commands to the app.

### Files created
- `src/tui/commands.py`

### Files modified
- `src/tui/widgets/chat_panel.py`

### commands.py

```python
COMMANDS = {
    "download": "Last ned data fra FootyStats",
    "train": "Tren ML-modeller",
    "predict": "Finn value bets for kommende kamper",
    "help": "Vis tilgjengelige kommandoer",
    "clear": "Nullstill chat-historikk",
    "status": "Vis naavaerende status (data, modell)",
}

def parse_command(text: str) -> ChatCommand | None: ...
```

### chat_panel.py changes

In `on_input_submitted`, before sending to LLM:
1. Call `parse_command(text)`
2. If command: `/clear` (existing), `/help` (render inline), `/download`/`/train`/`/predict` (post `CommandRequested` Message), unknown (error inline)
3. If not command: proceed with LLM flow

New Message: `ChatPanel.CommandRequested(command, args)`

### Verification
- `/help` shows formatted command list inline
- `/clear` clears chat
- `/download` posts CommandRequested message
- Regular text still goes to LLM
- `/foobar` shows "Ukjent kommando" error

---

## Phase 3: Rewire App Layout (The Big Switch)

Replace tab-based layout with chat-first layout. Most impactful phase.

### Files modified
- `src/tui/app.py` - Complete layout rewrite
- `src/tui/styles/app.tcss` - New CSS layout
- `src/tui/widgets/chat_panel.py` - Remove dock/height constraints

### app.py changes

New `compose()`:
```python
def compose(self) -> ComposeResult:
    with Horizontal(id="main-content"):
        yield ChatPanel(id="chat-panel")
        with Vertical(id="right-panel"):
            yield DataQualityPanel(id="data-quality")
            yield ActivityPanel(id="activity-panel")
            yield EventLog(id="event-log", markup=True)
    yield Footer()
```

New `BINDINGS` (remove Ctrl+D/T/P, keep Escape + Ctrl+Q).

New handler `on_chat_panel_command_requested()` routes `/commands` to `_start_download()`, `_start_training()`, `_start_predictions()`.

Update all message handlers to use new widgets (DataQualityPanel.refresh instead of StatusBar, ActivityPanel.set_task/clear_task instead of spinner).

### app.tcss changes

```css
#main-content { layout: horizontal; height: 1fr; }
ChatPanel { width: 1fr; }
#right-panel { layout: vertical; width: 32; border-left: solid $accent; }
DataQualityPanel { height: auto; max-height: 12; }
ActivityPanel { height: 8; }
EventLog { height: 1fr; }
```

### Verification
- New layout renders correctly
- `/download`, `/train`, `/predict` trigger workers correctly
- ActivityPanel shows spinner during tasks
- DataQualityPanel refreshes after tasks complete
- EventLog receives log messages
- Escape cancels, Ctrl+Q exits

---

## Phase 4: Inline Results Rendering in Chat

Render predictions and training reports inline in chat instead of in removed tab widgets.

### Files modified
- `src/tui/widgets/chat_panel.py`
- `src/tui/app.py`

### New ChatPanel methods

- `render_predictions_inline(picks, stale_warning)` - Markdown table with predictions
- `render_training_report_inline(report)` - Markdown table with model accuracies
- `render_system_message(text)` - System messages (download summaries)

### app.py routing

- `on_prediction_finished` -> `chat_panel.render_predictions_inline(picks)` then auto-analysis
- `on_training_finished` -> `chat_panel.render_training_report_inline(report)` then auto-predict
- `on_download_finished` -> `chat_panel.render_system_message(summary)`

### Verification
- `/predict` renders predictions table inline in chat
- `/train` renders training report inline
- `/download` shows summary message in chat
- Auto-analysis still streams after predictions
- Large tables scroll correctly

---

## Phase 5: Welcome Message with Auto-Detection

On startup, post a welcome message with current state.

### Files modified
- `src/tui/widgets/chat_panel.py`
- `src/tui/app.py`

### Welcome message logic

`show_welcome_message()`:
- Query DB for match count, league count, latest date
- Check model file and training report
- Render contextual message:
  - No data: suggest `/download`
  - Data but no model: suggest `/train`
  - Stale data (>30 days): show warning
  - All ready: show stats, suggest `/predict`

### Verification
- Start with data + model: shows stats + suggests `/predict`
- Start with no data: suggests `/download`
- Start with stale data: shows warning

---

## Phase 6: Cleanup and Polish

Remove old widgets, update docs, handle edge cases.

### Files deleted
- `src/tui/widgets/status_bar.py`
- `src/tui/widgets/predictions_view.py`
- `src/tui/widgets/data_table_view.py`
- `src/tui/widgets/training_view.py`

### Files modified
- `SYSTEM.md` - Update TUI section
- `CLAUDE.md` - Update project structure and keybindings
- `src/tui/widgets/chat_panel.py` - Polish: input placeholder, command echoing, edge cases

### Edge cases
- Command while task running: show "En oppgave kjorer allerede"
- `/clear` clears welcome message too
- Terminal size warning still works

### Verification
- Full smoke test: `/download` -> `/train` -> `/predict` sequence
- No import errors from deleted widgets
- Documentation matches new behavior
- Minimum terminal size warning works
