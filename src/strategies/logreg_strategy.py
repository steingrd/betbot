"""
Logistic Regression strategy.

Linear baseline using the same features as XGBoost.
Acts as an overfitting detector — if XGBoost finds value but LogReg disagrees,
the edge may come from tree-based overfitting rather than real signal.
"""

import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from sklearn.preprocessing import LabelEncoder, StandardScaler

from models.match_predictor import MatchPredictor
from strategies.base import StrategyPredictionError, StrategyTrainingError, TrainingResult


class LogRegStrategy:
    """Logistic Regression with same features as XGBoost."""

    FEATURE_COLS = MatchPredictor.FEATURE_COLS

    @property
    def name(self) -> str:
        return "LogReg"

    @property
    def slug(self) -> str:
        return "logreg"

    @property
    def supported_markets(self) -> list[str]:
        return ["H", "D", "A", "Over 2.5", "BTTS"]

    def __init__(self) -> None:
        self._scaler = StandardScaler()
        self._label_encoder = LabelEncoder()
        self._result_model: LogisticRegression | None = None
        self._over25_model: LogisticRegression | None = None
        self._btts_model: LogisticRegression | None = None
        self._fitted = False

    def train(
        self, matches_df: pd.DataFrame, features_df: pd.DataFrame
    ) -> TrainingResult:
        """Train 3 logistic regression models on feature data.

        Args:
            matches_df: Unused.
            features_df: DataFrame with FEATURE_COLS + target columns.
        """
        start = time.monotonic()

        try:
            X = features_df[self.FEATURE_COLS].fillna(0).values
        except KeyError as exc:
            raise StrategyTrainingError(self.slug, f"Missing feature columns: {exc}") from exc

        y_result = features_df["target_result"].values
        y_over25 = features_df["target_over_25"].values
        y_btts = features_df["target_btts"].values

        # Time-based split (80/20)
        if "date_unix" in features_df.columns:
            features_df_sorted = features_df.sort_values("date_unix")
            sort_idx = features_df_sorted.index
            X = features_df_sorted[self.FEATURE_COLS].fillna(0).values
            y_result = features_df_sorted["target_result"].values
            y_over25 = features_df_sorted["target_over_25"].values
            y_btts = features_df_sorted["target_btts"].values

        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]

        y_res_train, y_res_test = y_result[:split_idx], y_result[split_idx:]
        y_o25_train, y_o25_test = y_over25[:split_idx], y_over25[split_idx:]
        y_btts_train, y_btts_test = y_btts[:split_idx], y_btts[split_idx:]

        # Scale features
        X_train_scaled = self._scaler.fit_transform(X_train)
        X_test_scaled = self._scaler.transform(X_test)

        # Encode result labels
        y_res_train_enc = self._label_encoder.fit_transform(y_res_train)
        y_res_test_enc = self._label_encoder.transform(y_res_test)

        # 1X2 model (multiclass)
        self._result_model = LogisticRegression(C=1.0, max_iter=1000)
        self._result_model.fit(X_train_scaled, y_res_train_enc)

        # Over 2.5 model (binary)
        self._over25_model = LogisticRegression(C=1.0, max_iter=1000)
        self._over25_model.fit(X_train_scaled, y_o25_train)

        # BTTS model (binary)
        self._btts_model = LogisticRegression(C=1.0, max_iter=1000)
        self._btts_model.fit(X_train_scaled, y_btts_train)

        self._fitted = True
        duration = time.monotonic() - start

        # Evaluate on test set
        res_pred = self._result_model.predict(X_test_scaled)
        res_proba = self._result_model.predict_proba(X_test_scaled)
        o25_pred = self._over25_model.predict(X_test_scaled)
        o25_proba = self._over25_model.predict_proba(X_test_scaled)
        btts_pred = self._btts_model.predict(X_test_scaled)
        btts_proba = self._btts_model.predict_proba(X_test_scaled)

        return TrainingResult(
            accuracy={
                "result": float(accuracy_score(y_res_test_enc, res_pred)),
                "over25": float(accuracy_score(y_o25_test, o25_pred)),
                "btts": float(accuracy_score(y_btts_test, btts_pred)),
            },
            log_loss={
                "result": float(log_loss(y_res_test_enc, res_proba)),
                "over25": float(log_loss(y_o25_test, o25_proba)),
                "btts": float(log_loss(y_btts_test, btts_proba)),
            },
            num_samples=len(features_df),
            duration_seconds=round(duration, 2),
        )

    def predict(
        self, matches_df: pd.DataFrame, features_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Predict probabilities using logistic regression.

        Returns DataFrame with: match_id, prob_H, prob_D, prob_A, prob_over25, prob_btts.
        """
        if not self._fitted:
            raise StrategyPredictionError(self.slug, "Model not fitted")

        try:
            X = features_df[self.FEATURE_COLS].fillna(0).values
        except KeyError as exc:
            raise StrategyPredictionError(self.slug, f"Missing feature columns: {exc}") from exc

        X_scaled = self._scaler.transform(X)

        result_proba = self._result_model.predict_proba(X_scaled)
        result_classes = self._label_encoder.classes_

        over25_proba = self._over25_model.predict_proba(X_scaled)[:, 1]
        btts_proba = self._btts_model.predict_proba(X_scaled)[:, 1]

        out = pd.DataFrame({"match_id": features_df["match_id"].values})
        for i, cls in enumerate(result_classes):
            out[f"prob_{cls}"] = result_proba[:, i]

        out["prob_over25"] = over25_proba
        out["prob_btts"] = btts_proba
        return out

    def save(self, path: Path) -> None:
        """Save models to disk using joblib."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "scaler": self._scaler,
            "label_encoder": self._label_encoder,
            "result_model": self._result_model,
            "over25_model": self._over25_model,
            "btts_model": self._btts_model,
        }
        joblib.dump(data, path)

    def load(self, path: Path) -> bool:
        """Load models from disk."""
        if not path.exists():
            return False
        try:
            data = joblib.load(path)
            self._scaler = data["scaler"]
            self._label_encoder = data["label_encoder"]
            self._result_model = data["result_model"]
            self._over25_model = data["over25_model"]
            self._btts_model = data["btts_model"]
            self._fitted = True
            return True
        except Exception:
            return False

    @property
    def is_fitted(self) -> bool:
        return self._fitted
