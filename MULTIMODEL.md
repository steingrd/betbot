---
title: Multi-Strategy Consensus Value Betting System
type: feat
status: active
date: 2026-02-26
deepened: 2026-02-26
---

# Multi-Strategy Consensus Value Betting System

## Enhancement Summary

**Deepened on:** 2026-02-26
**Research agents used:** Dixon-Coles specialist, Elo ratings specialist, sklearn/ensemble researcher, architecture strategist, performance oracle, code simplicity reviewer, React UI researcher, Python code reviewer

### Critical Corrections from Research
1. **sklearn MLPClassifier has NO dropout parameter** -- the original plan was wrong. Use `alpha` (L2 regularization) instead
2. **Dataset is 169,545 matches, not ~5,000** -- this changes performance profiles dramatically
3. **Dixon-Coles will NOT converge on the full dataset** (6,187 parameters) -- must scope per-league
4. **MLP takes 41 seconds to train** on the full dataset -- defer to v2
5. **Feature generation is the bottleneck** (25 minutes full rebuild), not model training

### Key Simplifications Applied
- Deleted `registry.py` -- use a plain list of strategies
- Deleted `manifest.py` -- merge into existing training report
- Deferred MLP to v2 -- ship with 4 strategies
- Deferred StrategyPerformanceCard, expandable rows, and enable/disable checkboxes to v2
- Collapsed 12 implementation phases to 7 with a go/no-go gate after backtest

---

## Overview

Replace the single XGBoost model with 4 fundamentally different prediction strategies. Only surface value bets where a configurable number of strategies independently agree there is value. This consensus approach should produce higher-conviction picks than any single model.

**The 4 Strategies (v1):**

| # | Strategy | Type | Produces | Training Time |
|---|----------|------|----------|--------------|
| 1 | XGBoost | ML (trees) | 1X2, O2.5, BTTS | ~1s |
| 2 | Poisson/Dixon-Coles | Statistical | 1X2, O2.5, BTTS | ~5-15s (per-league) |
| 3 | Elo Ratings | Rating system | 1X2 only | ~0.1s |
| 4 | Logistic Regression | ML (linear) | 1X2, O2.5, BTTS | ~0.5s |

**Deferred to v2:** Neural Network (MLP) -- adds 41s training time, uses same features as XGBoost/LogReg so limited diversity benefit, and sklearn's `MLPClassifier` lacks dropout (the primary overfitting guard for neural nets).

**Key Decisions:**
- **Consensus = per-market-per-match.** Each (match, market) pair is evaluated independently.
- **"Agree" = each independently finds value.** Edge >= min_edge. Strategies can differ in probabilities.
- **Consensus threshold configurable via UI ToggleGroup** (not slider -- only 4-5 discrete values). Default: 2.
- **Client-side filtering.** Backend computes edge/is_value server-side, returns per-strategy results. UI filters by `consensus_count >= threshold` instantly.
- **Sequential training** with per-strategy progress.
- **Each strategy saves independently.** If one fails, others are preserved.
- **Elo supports 1X2 only.** Consensus denominator is per-market: 4 for 1X2, 3 for O2.5 and BTTS.
- **Go/no-go gate:** Run backtest comparing consensus vs individual strategies BEFORE building UI changes. If consensus does not improve ROI, stop.

---

## Technical Approach

### Architecture

```
src/
  strategies/
    __init__.py          # STRATEGIES list + helpers
    base.py              # Strategy protocol + TrainingResult + StrategyError
    consensus.py         # ConsensusEngine
    xgboost_strategy.py  # Wraps existing MatchPredictor
    poisson_strategy.py  # Dixon-Coles model (per-league)
    elo_strategy.py      # Elo rating system (Davidson model)
    logreg_strategy.py   # Logistic Regression
```

No `registry.py` (plain list), no `manifest.py` (merged into training report).

### Phase 1: Strategy Protocol

**File: `src/strategies/base.py`**

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

import pandas as pd


@dataclass(frozen=True, slots=True)
class TrainingResult:
    """Immutable result from a strategy training run."""
    accuracy: dict[str, float | None]    # per-market accuracy
    log_loss: dict[str, float | None]    # per-market log loss
    num_samples: int
    duration_seconds: float
    metadata: dict[str, str] = field(default_factory=dict)


class StrategyError(Exception):
    """Base exception for strategy failures."""
    def __init__(self, strategy_slug: str, message: str) -> None:
        self.strategy_slug = strategy_slug
        super().__init__(f"[{strategy_slug}] {message}")


class StrategyTrainingError(StrategyError):
    pass


class StrategyPredictionError(StrategyError):
    pass


@runtime_checkable
class Strategy(Protocol):
    """Common interface for all prediction strategies."""

    @property
    def name(self) -> str:
        """Human-readable name, e.g. 'XGBoost'."""
        ...

    @property
    def slug(self) -> str:
        """Machine-friendly identifier, e.g. 'xgboost'."""
        ...

    @property
    def supported_markets(self) -> list[str]:
        """Markets this strategy can predict.
        Subset of ['H', 'D', 'A', 'Over 2.5', 'BTTS']."""
        ...

    def train(self, matches_df: pd.DataFrame, features_df: pd.DataFrame) -> TrainingResult:
        """Train on historical data. Returns structured result."""
        ...

    def predict(self, matches_df: pd.DataFrame, features_df: pd.DataFrame) -> pd.DataFrame:
        """Predict probabilities. Returns DataFrame with columns:
        match_id, prob_H, prob_D, prob_A, prob_over25, prob_btts
        (NaN for unsupported markets)."""
        ...

    def save(self, path: Path) -> None:
        """Persist trained model to disk."""
        ...

    def load(self, path: Path) -> bool:
        """Load trained model from disk. Returns True if successful."""
        ...

    @property
    def is_fitted(self) -> bool:
        """Whether the strategy has been trained."""
        ...
```

**Research insights applied:**
- `pathlib.Path` instead of `str` for file paths (Python 3.4+ best practice)
- `TrainingResult` dataclass instead of bare `dict` -- type-safe, immutable, discoverable
- Custom exception hierarchy (`StrategyError` -> `StrategyTrainingError`, `StrategyPredictionError`) for structured error handling
- Kept `matches_df` + `features_df` as separate params: strategies with different data needs (Poisson uses matches, XGBoost uses features) select what they need. Merging into a single `StrategyInput` added complexity without benefit since the two DataFrames have different schemas.

**File: `src/strategies/__init__.py`**

```python
from .xgboost_strategy import XGBoostStrategy
from .poisson_strategy import PoissonStrategy
from .elo_strategy import EloStrategy
from .logreg_strategy import LogRegStrategy

# Plain list. No registry class needed for 4 strategies.
STRATEGIES: list = [
    XGBoostStrategy(),
    PoissonStrategy(),
    EloStrategy(),
    LogRegStrategy(),
]

def get_fitted() -> list:
    return [s for s in STRATEGIES if s.is_fitted]

def for_market(market: str) -> list:
    return [s for s in STRATEGIES if market in s.supported_markets]
```

### Phase 2: Strategy Implementations

#### 2a. XGBoost Strategy (`src/strategies/xgboost_strategy.py`)

Adapter around existing `MatchPredictor`. Minimal changes.

- `supported_markets`: all 5 (H, D, A, Over 2.5, BTTS)
- Delegates to existing `MatchPredictor.train/predict/save/load`
- Persistence: `joblib` (not pickle -- 20-50% faster for numpy-heavy objects, already a sklearn dependency)

#### 2b. Poisson/Dixon-Coles Strategy (`src/strategies/poisson_strategy.py`)

Classical statistical model for football. **Must be scoped per-league** due to dataset size (169k matches, 3,093 teams = 6,187 parameters -- won't converge globally).

**Dixon-Coles model specifics:**

Parameters per league:
- `alpha_i` (attack strength per team)
- `beta_i` (defense strength per team)
- `gamma` (home advantage)
- `rho` (low-score correlation correction, typically -0.10 to -0.15)

Expected goals: `lambda_home = exp(alpha_home + beta_away + gamma)`, `lambda_away = exp(alpha_away + beta_home)`

**Tau correction** for low-scoring outcomes (0-0, 1-0, 0-1, 1-1):
```python
def tau_correction(x, y, lambda_x, mu_y, rho):
    if x == 0 and y == 0: return 1 - (lambda_x * mu_y * rho)
    elif x == 0 and y == 1: return 1 + (lambda_x * rho)
    elif x == 1 and y == 0: return 1 + (mu_y * rho)
    elif x == 1 and y == 1: return 1 - rho
    else: return 1.0
```

**Implementation approach:**
- **Sum-to-zero trick** on defense parameters (eliminates equality constraint, allows L-BFGS-B instead of SLSQP, 5-7x faster)
- Optimizer: `scipy.optimize.minimize` with `method='L-BFGS-B'`, bounds on rho `[-0.5, 0.5]`
- **Time decay: xi = 0.001 per day** (match from 1 year ago gets weight 0.694). Tune via cross-validation over `[0.0005, 0.001, 0.002, 0.003, 0.005]`
- **Data window: Last 4 seasons** per league (best performance per penaltyblog 2025 analysis)
- **Goal matrix: max_goals = 7** (8x8 matrix). Verify `np.sum(matrix) > 0.999`

**Market derivation from goal matrix M[i,j]:**
```python
prob_H = np.sum(np.tril(M, -1))      # below diagonal
prob_D = np.sum(np.diag(M))           # diagonal
prob_A = np.sum(np.triu(M, 1))        # above diagonal
prob_over25 = 1 - (M[0,0] + M[0,1] + M[0,2] + M[1,0] + M[1,1] + M[2,0])
prob_btts = np.sum(M[1:, 1:])
```

**Calibration caveat:** Standard Poisson tends to under-estimate goal totals (over-dispersion). Monitor O2.5 calibration and consider post-hoc isotonic calibration if systematic bias detected.

**Validation checks:**
- rho = 0 must produce identical results to independent Poisson
- rho should be negative on real data (-0.10 to -0.15)
- gamma should be positive (~0.25-0.30)
- `np.sum(goal_matrix)` must be > 0.999
- RPS benchmark: ~0.189-0.192 for major European leagues

**Performance (per-league):**
- 20 teams, 380 matches: ~0.01s
- 100 teams, 5000 matches: ~0.4s
- Total across ~10-15 active leagues: ~5-15s

**Persistence:** Save per-league parameters as JSON dict. Use `joblib` only if needed.

**Reference:** Consider using `penaltyblog` (`pip install penaltyblog`) as a reference implementation for validation, but implement from scratch for full control.

#### 2c. Elo Rating Strategy (`src/strategies/elo_strategy.py`)

Rating-based system using the **Davidson model** for three-outcome prediction (more principled than ad-hoc draw probability calibration).

- `supported_markets`: 1X2 only (H, D, A)
- **Separate per-league ratings** (no cross-league calibration needed since we compare within leagues)
- Rating persistence: JSON dict saved to disk

**Davidson model for probabilities:**
```python
def davidson_probs(r_home, r_away, home_advantage=80, nu=0.85):
    dr = (r_home + home_advantage - r_away) / 400.0
    gamma_h = 10 ** (dr / 2)
    gamma_a = 10 ** (-dr / 2)
    denom = gamma_h + gamma_a + nu * math.sqrt(gamma_h * gamma_a)
    return gamma_h / denom, nu * math.sqrt(gamma_h * gamma_a) / denom, gamma_a / denom
```

**Key parameters:**

| Parameter | Value | Notes |
|-----------|-------|-------|
| K-factor | 20 (base) | With goal-diff multiplier |
| Home advantage | 80 Elo points | Fit per-league from data |
| Draw parameter (nu) | 0.85 | Davidson model; fit to observed draw rate |
| Season regression | 1/3 toward 1500 | Apply between seasons |
| Cold start | League mean - 100 | K doubled for first 10 matches |

**FiveThirtyEight goal-difference multiplier:**
```python
def goal_diff_multiplier(goal_diff, elo_diff):
    if goal_diff <= 1: base = 1.0
    elif goal_diff == 2: base = 1.5
    else: base = (11 + goal_diff) / 8.0
    # Autocorrelation correction (prevent over-rewarding favorites)
    correction = 2.2 / (abs(elo_diff) * 0.001 + 2.2)
    return base * correction
```

**Performance:** 0.118 seconds for all 169,545 matches. No bottleneck.

#### 2d. Logistic Regression Strategy (`src/strategies/logreg_strategy.py`)

Linear baseline using the same features as XGBoost. Acts as an **overfitting detector** -- if XGBoost finds value but LogReg disagrees, the edge may be from tree-based overfitting.

- `supported_markets`: all 5
- Same `FEATURE_COLS`, same scaler as XGBoost
- 3 separate `LogisticRegression` models (1X2 multiclass, O2.5 binary, BTTS binary)
- `C=1.0`, `max_iter=1000`. LogReg is naturally well-calibrated -- no isotonic calibration needed
- Persistence: `joblib`
- **Training time:** ~0.5s

### Phase 3: Consensus Engine

**File: `src/strategies/consensus.py`**

```python
from pydantic import BaseModel, Field


class StrategySignal(BaseModel):
    """A single strategy's prediction for a market."""
    strategy_slug: str
    strategy_name: str
    model_prob: float = Field(ge=0.0, le=1.0)
    edge: float
    is_value: bool


class ConsensusBet(BaseModel):
    """Aggregated consensus for a match-market pair."""
    match_id: str
    home_team: str
    away_team: str
    league: str
    kickoff: str
    market: str
    odds: float = Field(gt=0.0)
    implied_prob: float = Field(ge=0.0, le=1.0)
    consensus_count: int
    total_strategies: int
    signals: list[StrategySignal]

    @property
    def agreement_ratio(self) -> float:
        if not self.signals:
            return 0.0
        return sum(1 for s in self.signals if s.is_value) / len(self.signals)


class ConsensusEngine:
    """Finds value bets where multiple strategies agree."""

    def find_consensus_bets(
        self,
        strategy_predictions: dict[str, pd.DataFrame],
        odds_df: pd.DataFrame,  # match_id, market, odds, implied_prob
        min_edge: float = 0.05,
        min_consensus: int = 2,
    ) -> list[ConsensusBet]:
        ...
```

**Research insights applied:**
- `ConsensusBet` uses **Pydantic BaseModel** (not dataclass) because it crosses the API boundary -- gets automatic JSON serialization, validation, and schema generation
- `StrategyDetail` replaced with `StrategySignal` as a Pydantic model in a `list` (not a dict) for cleaner iteration
- Odds passed explicitly in `odds_df`, not buried in `features_df` -- makes the data dependency clear
- Edge computed server-side (including `normalize_1x2_probs`). Client just filters by `consensus_count`

**Consensus denominator is per-market:**
- 1X2 markets (H, D, A): all 4 strategies vote
- Over 2.5: 3 strategies vote (no Elo)
- BTTS: 3 strategies vote (no Elo)

### Phase 4: Training Pipeline Update

**File: `src/services/tasks.py` -- update `run_training()`**

Feature generation dominates training time (25 min full rebuild vs ~20s for all models). Progress bands must reflect this:

```
0-5%    Load data from database
5-70%   Generate features (shared, with incremental cache)
70-75%  Strategy 1/4: XGBoost
75-80%  Strategy 2/4: Poisson/Dixon-Coles (per-league)
80-85%  Strategy 3/4: Elo
85-90%  Strategy 4/4: Logistic Regression
90-95%  Quick backtest (all strategies on hold-out)
95-100% Save models + training report
```

**Progress events:**
```python
TrainingProgress(
    step="Poisson/Dixon-Coles",
    detail="Fitting Premier League (15/31 leagues)...",
    percent=77,
    strategy_index=2,
    strategy_total=4,
)
```

**Error handling pattern:**
```python
results: dict[str, TrainingResult] = {}
errors: dict[str, str] = {}

for strategy in STRATEGIES:
    try:
        results[strategy.slug] = strategy.train(matches_df, features_df)
    except StrategyTrainingError as exc:
        logger.error("Strategy '%s' failed: %s", strategy.slug, exc)
        errors[strategy.slug] = str(exc)
    except Exception as exc:
        logger.exception("Unexpected error training '%s'", strategy.slug)
        errors[strategy.slug] = str(exc)
```

If only 1 strategy succeeds, warn: "Consensus requires at least 2 strategies."

**Backtest at training time:** Run hold-out backtest for all strategies + consensus at N=2,3,4. Store per-strategy metrics in training report (extends existing `reports/latest_training_report.json`).

### Phase 5: Prediction Pipeline Update

**File: `src/predictions/daily_picks.py` -- refactor to use strategies**

1. Load all fitted strategies (check `strategy.is_fitted` after `load()`)
2. Fetch upcoming matches from Norsk Tipping
3. Compute features once (shared)
4. Each strategy predicts independently. Skip failed strategies with warning.
5. Run `ConsensusEngine.find_consensus_bets()` -- returns all bets at min_consensus=1
6. Cache full results to `data/processed/latest_predictions.json`

**API response shape (match-centric, avoids data duplication):**

```json
{
  "generated_at": "2026-02-26T14:30:00",
  "predictions": [
    {
      "match_id": "...",
      "home_team": "Arsenal",
      "away_team": "Chelsea",
      "league": "Premier League",
      "kickoff": "2026-02-27T20:00",
      "market": "Draw",
      "odds": 3.50,
      "implied_prob": 0.286,
      "consensus_count": 3,
      "total_strategies": 4,
      "signals": [
        { "strategy_slug": "xgboost", "strategy_name": "XGBoost", "model_prob": 0.35, "edge": 0.064, "is_value": true },
        { "strategy_slug": "poisson", "strategy_name": "Poisson", "model_prob": 0.32, "edge": 0.034, "is_value": false },
        { "strategy_slug": "elo",     "strategy_name": "Elo",     "model_prob": 0.38, "edge": 0.094, "is_value": true },
        { "strategy_slug": "logreg",  "strategy_name": "LogReg",  "model_prob": 0.33, "edge": 0.044, "is_value": true }
      ]
    }
  ],
  "strategy_backtest": {
    "xgboost": { "roi": 8.2, "win_rate": 0.42, "total_bets": 150 },
    "poisson": { "roi": 5.1, "win_rate": 0.38, "total_bets": 120 },
    "elo":     { "roi": 3.0, "win_rate": 0.35, "total_bets": 90 },
    "logreg":  { "roi": 4.5, "win_rate": 0.40, "total_bets": 140 }
  }
}
```

### Phase 6: API + Web UI Updates

**API changes:**
- `GET /api/predictions/latest` -- return full prediction structure with signals
- `GET /api/data/status` -- add `strategies: list[{slug, name, trained_at}]`
- SSE progress events include `strategy_index` and `strategy_total`

**TypeScript types:**

```typescript
interface StrategySignal {
  strategy_slug: string
  strategy_name: string
  model_prob: number
  edge: number
  is_value: boolean
}

interface Prediction {
  match_id: string
  home_team: string
  away_team: string
  league: string
  kickoff: string
  market: string
  odds: number
  implied_prob: number
  consensus_count: number
  total_strategies: number
  signals: StrategySignal[]
}
```

**Consensus ToggleGroup** (not Slider -- only 4 discrete values):
```tsx
<ToggleGroup type="single" value={String(threshold)} onValueChange={v => v && setThreshold(Number(v))}>
  {[1, 2, 3, 4].map(n => <ToggleGroupItem key={n} value={String(n)}>{n}</ToggleGroupItem>)}
</ToggleGroup>
```
Install: `npx shadcn@latest add toggle-group`

**Client-side filtering pattern:**
```tsx
const filteredPredictions = useMemo(
  () => predictions.filter(p => p.consensus_count >= threshold),
  [predictions, threshold]
)
```

**PredictionsTable changes:**
- Add "Enighet" column showing "3/4"
- Consensus count badge (color-coded by strength)
- Show average probability across agreeing strategies

**Progress bar update:**
- Show "Trener strategi 2/4: Poisson... (77%)"
- Segmented dot indicator below bar showing which strategies are complete

**StatusMetricsRow update:**
- "4 strategier trent" (or "3/4 trent" if one failed)
- Last trained timestamp

### Phase 7: Backtest Script Update

**File: `scripts/run_backtest.py`**

This is the **go/no-go gate**. Run before building UI.

1. Train all 4 strategies on training split (shared split, same for all)
2. Each strategy predicts on hold-out split
3. Per-strategy backtest (ROI, win rate, 95% CI via bootstrap)
4. Consensus backtest at N=2,3,4
5. Print comparison table

```
=== Per-Strategy Backtest ===
Strategy      | Bets | Win% | ROI    | 95% CI
XGBoost       | 150  | 42%  | +8.2%  | [-2%, +18%]
Poisson       | 120  | 38%  | +5.1%  | [-5%, +15%]
Elo (1X2)     | 90   | 35%  | +3.0%  | [-8%, +14%]
LogReg        | 140  | 40%  | +4.5%  | [-3%, +12%]

=== Consensus Backtest ===
Min Consensus | Bets | Win% | ROI    | 95% CI
2 of N        | 95   | 45%  | +12.0% | [+1%, +23%]
3 of N        | 55   | 50%  | +18.0% | [+3%, +33%]
4 of N        | 20   | 55%  | +22.0% | [-5%, +49%]

=== Verdict ===
Best individual:  XGBoost (+8.2% ROI)
Best consensus:   3 of N (+18.0% ROI)
Consensus improvement: +9.8% ROI over best individual
```

**If consensus does not improve ROI:** Stop. The multi-strategy approach is not worth the UI complexity. Continue using the single XGBoost model.

**If consensus improves ROI:** Proceed to Phase 6 (API + UI integration).

---

## Implementation Phases (Collapsed)

### Phase 1: Strategy Protocol + XGBoost Adapter
- [ ] Create `src/strategies/base.py` -- Strategy protocol, TrainingResult, StrategyError
- [ ] Create `src/strategies/__init__.py` -- STRATEGIES list, helper functions
- [ ] Create `src/strategies/xgboost_strategy.py` -- adapter around existing MatchPredictor
- [ ] Switch model persistence from pickle to joblib
- [ ] Verify XGBoost adapter produces identical results to current system

### Phase 2: Implement Poisson/Dixon-Coles
- [ ] Create `src/strategies/poisson_strategy.py`
- [ ] Implement per-league parameter estimation (sum-to-zero trick + L-BFGS-B)
- [ ] Implement Dixon-Coles tau correction for low-scoring games
- [ ] Implement time decay weighting (xi=0.001 default)
- [ ] Implement goal matrix (8x8) -> 1X2, O2.5, BTTS derivation
- [ ] Validate: rho < 0, gamma > 0, matrix sums to ~1.0, rho=0 matches independent Poisson

### Phase 3: Implement Elo Ratings
- [ ] Create `src/strategies/elo_strategy.py`
- [ ] Implement Davidson model for 3-outcome probabilities
- [ ] Implement FiveThirtyEight goal-difference multiplier with autocorrelation correction
- [ ] Implement per-league rating system with season regression (1/3 toward 1500)
- [ ] Handle cold-start (league mean - 100, doubled K for first 10 matches)
- [ ] Persist ratings as JSON

### Phase 4: Implement Logistic Regression
- [ ] Create `src/strategies/logreg_strategy.py`
- [ ] Reuse FEATURE_COLS and scaler from XGBoost
- [ ] 3 separate LogisticRegression models (1X2 multiclass, O2.5 binary, BTTS binary)

### Phase 5: Consensus Engine + Backtest Validation (GO/NO-GO GATE)
- [ ] Create `src/strategies/consensus.py` -- ConsensusEngine, ConsensusBet (Pydantic)
- [ ] Implement per-market-per-match consensus with variable denominators
- [ ] Update `scripts/run_backtest.py` for multi-strategy evaluation
- [ ] Run backtest: individual vs consensus at N=2,3,4
- [ ] **DECISION POINT:** If consensus does not improve ROI, stop here

### Phase 6: Training + Prediction Pipeline Integration
- [ ] Update `src/services/tasks.py` `run_training()` for sequential multi-strategy training
- [ ] Add per-strategy progress events (strategy_index, strategy_total)
- [ ] Handle partial failure (continue on error)
- [ ] Run backtest at training time, store in training report
- [ ] Refactor `DailyPicksFinder` to use ConsensusEngine
- [ ] Update prediction cache format

### Phase 7: API + Web UI
- [ ] Update `GET /api/predictions/latest` response format
- [ ] Update `GET /api/data/status` with strategy info
- [ ] Update SSE progress events
- [ ] Update TypeScript types
- [ ] Add consensus ToggleGroup to PredictionsCard (install `toggle-group`)
- [ ] Add "Enighet" column to PredictionsTable
- [ ] Update progress bar with strategy name + segmented dots
- [ ] Update StatusMetricsRow for multi-strategy

---

## Performance Considerations

| Component | Measured Time | Notes |
|-----------|--------------|-------|
| Feature generation (full) | ~25 min | Incremental cache reduces to seconds |
| XGBoost training | ~1s | Fast |
| Poisson (all leagues) | ~5-15s | Per-league, each <0.5s |
| Elo computation | 0.12s | O(n), trivial |
| LogReg training | ~0.5s | Fast |
| Backtest (all strategies) | ~5s | Predict + bootstrap CI |
| **Total training** | **~20-30s** | Plus feature gen (cached) |

**Critical performance fix:** `_get_season_position()` in `feature_engineering.py` is O(n) without `season_id` (2.5s per call). Always pass `season_id`. Vectorize the inner `iterrows()` loop with `groupby().agg()`.

**Memory:** All 4 models total < 5 MB in memory. The dominant consumers are DataFrames (~250-300 MB peak during training). Fine for single-user server.

---

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Consensus does not improve ROI | Medium | High | **Go/no-go gate at Phase 5.** Backtest before building UI. |
| Dixon-Coles fails to converge | Low (per-league) | Low | Per-league fitting keeps parameter count < 50. Monitor convergence. |
| Elo cold-start for promoted teams | Certain | Low | Default rating: league mean - 100. K doubled for first 10 matches. |
| Feature generation bottleneck | High | Medium | Incremental caching already exists. Fix `_get_season_position()`. |
| Poisson under-predicts O2.5 | Medium | Low | Known calibration issue. Monitor and add isotonic calibration if needed. |

---

## Open Questions (Resolved)

| Question | Resolution |
|----------|-----------|
| Consensus threshold default 2 or 3? | **2.** Less restrictive, user can increase. |
| Elo persist or recalculate? | **Recalculate from scratch.** Reproducibility trumps speed (0.12s anyway). |
| Backtest before UI? | **Yes.** Phase 5 is a go/no-go gate. |
| Registry pattern? | **No.** Plain list of 4 strategies. |
| Manifest file? | **No.** Extend existing training report JSON. |
| MLP in v1? | **No.** Deferred to v2 (41s training, same features as XGBoost/LogReg). |
| Expandable rows? | **Deferred to v2.** Consensus count column is sufficient for v1. |
| Strategy enable/disable UI? | **Deferred to v2.** |

---

## Files Changed

### New files
- `src/strategies/__init__.py`
- `src/strategies/base.py`
- `src/strategies/consensus.py`
- `src/strategies/xgboost_strategy.py`
- `src/strategies/poisson_strategy.py`
- `src/strategies/elo_strategy.py`
- `src/strategies/logreg_strategy.py`

### Modified files
- `src/services/tasks.py` -- multi-strategy training loop
- `src/predictions/daily_picks.py` -- consensus prediction pipeline
- `src/api/routes/predictions.py` -- updated response format
- `src/api/routes/data.py` -- strategy status
- `src/api/routes/tasks.py` -- enhanced progress events
- `web/src/types/index.ts` -- new types
- `web/src/components/predictions/PredictionsCard.tsx` -- consensus ToggleGroup
- `web/src/components/predictions/PredictionsTable.tsx` -- consensus column
- `web/src/components/dashboard/ActionsBar.tsx` -- strategy name in progress
- `web/src/components/dashboard/StatusMetricsRow.tsx` -- multi-strategy summary
- `web/src/hooks/usePredictions.ts` -- updated data shape
- `scripts/run_backtest.py` -- multi-strategy evaluation

---

## v2 Enhancements (Deferred)

- MLP strategy (5th model)
- StrategyPerformanceCard with enable/disable checkboxes
- Expandable table rows showing per-strategy probabilities
- Weighted consensus (weight by backtest ROI)
- Per-market consensus thresholds
- `penaltyblog` integration for Dixon-Coles validation

---

## References

- [Dixon & Coles (1997)](https://opisthokonta.net/?cat=48) -- Original paper and implementation series
- [penaltyblog model comparison (2025)](https://pena.lt/y/2025/03/10/which-model-should-you-use-to-predict-football-matches/) -- Dixon-Coles RPS ~0.189, xi=0.001 optimal
- [dashee87 Dixon-Coles tutorial](https://dashee87.github.io/football/python/predicting-football-results-with-statistical-modelling-dixon-coles-and-time-weighting/) -- Python implementation reference
- [opisthokonta sum-to-zero trick](https://opisthokonta.net/?p=939) -- 5-7x speedup for parameter estimation
- [Davidson (1970)](https://en.wikipedia.org/wiki/Bradley%E2%80%93Terry_model#Ties) -- Three-outcome paired comparison model
- [Hvattum & Arntzen (2010)](https://www.researchgate.net/publication/222665781) -- Elo ratings for football, K~20
- [Shwartz-Ziv & Armon (2022)](https://arxiv.org/abs/2106.03253) -- XGBoost + MLP ensemble improves over either alone
- [sklearn MLPClassifier docs](https://scikit-learn.org/stable/modules/generated/sklearn.neural_network.MLPClassifier.html) -- No dropout; use alpha for regularization
- [Shadcn ToggleGroup](https://ui.shadcn.com/docs/components/radix/toggle-group) -- Discrete selector component
