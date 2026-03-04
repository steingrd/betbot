"""
Strategy base types.

Defines the Strategy protocol, TrainingResult, and error hierarchy
used by all prediction strategies.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

import pandas as pd


@dataclass(frozen=True, slots=True)
class TrainingResult:
    """Immutable result from a strategy training run."""

    accuracy: dict[str, float | None]
    log_loss: dict[str, float | None]
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

    def train(
        self, matches_df: pd.DataFrame, features_df: pd.DataFrame
    ) -> TrainingResult:
        """Train on historical data. Returns structured result."""
        ...

    def predict(
        self, matches_df: pd.DataFrame, features_df: pd.DataFrame
    ) -> pd.DataFrame:
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
