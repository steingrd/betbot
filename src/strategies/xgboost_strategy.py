"""
XGBoost strategy — adapter around existing MatchPredictor.

Wraps the existing XGBoost-based model to conform to the Strategy protocol.
"""

import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from models.match_predictor import MatchPredictor
from strategies.base import StrategyPredictionError, StrategyTrainingError, TrainingResult


class XGBoostStrategy:
    """XGBoost ensemble with isotonic calibration (existing model)."""

    @property
    def name(self) -> str:
        return "XGBoost"

    @property
    def slug(self) -> str:
        return "xgboost"

    @property
    def supported_markets(self) -> list[str]:
        return ["H", "D", "A", "Over 2.5", "BTTS"]

    def __init__(self) -> None:
        self._predictor = MatchPredictor()

    def train(
        self, matches_df: pd.DataFrame, features_df: pd.DataFrame
    ) -> TrainingResult:
        """Train the XGBoost model on feature data.

        Args:
            matches_df: Raw match data (unused — XGBoost uses engineered features).
            features_df: DataFrame with FEATURE_COLS + target columns.
        """
        start = time.monotonic()
        try:
            results = self._predictor.train(features_df)
        except Exception as exc:
            raise StrategyTrainingError(self.slug, str(exc)) from exc
        duration = time.monotonic() - start

        return TrainingResult(
            accuracy={
                "result": results["result"]["accuracy"],
                "over25": results["over25"]["accuracy"],
                "btts": results["btts"]["accuracy"],
            },
            log_loss={
                "result": results["result"]["log_loss"],
                "over25": results["over25"]["log_loss"],
                "btts": results["btts"]["log_loss"],
            },
            num_samples=len(features_df),
            duration_seconds=round(duration, 2),
        )

    def predict(
        self, matches_df: pd.DataFrame, features_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Predict probabilities using the XGBoost model.

        Returns DataFrame with: match_id, prob_H, prob_D, prob_A, prob_over25, prob_btts
        """
        if not self.is_fitted:
            raise StrategyPredictionError(self.slug, "Model not fitted")

        try:
            preds = self._predictor.predict(features_df)
        except Exception as exc:
            raise StrategyPredictionError(self.slug, str(exc)) from exc

        # Normalize output to standard columns
        out = pd.DataFrame({"match_id": preds["match_id"]})
        out["prob_H"] = preds["prob_H"]
        out["prob_D"] = preds["prob_D"]
        out["prob_A"] = preds["prob_A"]
        out["prob_over25"] = preds["prob_over25"]
        out["prob_btts"] = preds["prob_btts"]
        return out

    def save(self, path: Path) -> None:
        """Save model to disk using joblib."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "scaler": self._predictor.scaler,
            "label_encoder": self._predictor.label_encoder,
            "result_model": self._predictor.result_model,
            "over25_model": self._predictor.over25_model,
            "btts_model": self._predictor.btts_model,
        }
        joblib.dump(data, path)

    def load(self, path: Path) -> bool:
        """Load model from disk. Returns True if successful."""
        if not path.exists():
            return False
        try:
            data = joblib.load(path)
            self._predictor.scaler = data["scaler"]
            self._predictor.label_encoder = data["label_encoder"]
            self._predictor.result_model = data["result_model"]
            self._predictor.over25_model = data["over25_model"]
            self._predictor.btts_model = data["btts_model"]
            self._predictor.is_fitted = True
            return True
        except Exception:
            return False

    @property
    def is_fitted(self) -> bool:
        return self._predictor.is_fitted
