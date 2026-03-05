"""
Prediction strategies.

Plain list of all available strategies. No registry class needed.
"""

from strategies.base import Strategy, StrategyError, StrategyTrainingError, StrategyPredictionError, TrainingResult
from strategies.xgboost_strategy import XGBoostStrategy
from strategies.poisson_strategy import PoissonStrategy
from strategies.elo_strategy import EloStrategy
from strategies.logreg_strategy import LogRegStrategy

# Plain list. No registry class needed for 4 strategies.
STRATEGIES: list = [
    XGBoostStrategy(),
    PoissonStrategy(),
    EloStrategy(),
    LogRegStrategy(),
]


def get_fitted() -> list:
    """Return only strategies that have been trained."""
    return [s for s in STRATEGIES if s.is_fitted]


def for_market(market: str) -> list:
    """Return strategies that support a given market."""
    return [s for s in STRATEGIES if market in s.supported_markets]


def get_strategies(slugs: list[str]) -> list:
    """Return fresh strategy instances for the given slugs."""
    slug_to_cls = {
        "xgboost": XGBoostStrategy,
        "poisson": PoissonStrategy,
        "elo": EloStrategy,
        "logreg": LogRegStrategy,
    }
    result = []
    for slug in slugs:
        cls = slug_to_cls.get(slug)
        if cls is None:
            raise ValueError(f"Unknown strategy slug: {slug!r}")
        result.append(cls())
    return result
