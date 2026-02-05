"""
Match Predictor

ML models for predicting football match outcomes.
"""

import pickle
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.isotonic import IsotonicRegression
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, log_loss, classification_report, brier_score_loss


class _TimeCalibratedClassifier:
    """
    Wrapper that applies isotonic calibration to a fitted classifier.

    This implements time-based calibration by fitting isotonic regression
    on a held-out calibration set (later in time than training data).
    """

    def __init__(self, base_model, X_cal, y_cal):
        self.base_model = base_model
        self.classes_ = base_model.classes_
        self.calibrators = []

        # Get uncalibrated probabilities on calibration set
        uncalibrated_proba = base_model.predict_proba(X_cal)

        # Fit isotonic regression for each class
        n_classes = len(self.classes_)
        for i in range(n_classes):
            # Binary target: 1 if this class, 0 otherwise
            y_binary = (y_cal == self.classes_[i]).astype(int)

            # Fit isotonic regression
            iso = IsotonicRegression(out_of_bounds='clip')
            iso.fit(uncalibrated_proba[:, i], y_binary)
            self.calibrators.append(iso)

    def predict(self, X):
        """Predict class labels"""
        proba = self.predict_proba(X)
        return self.classes_[np.argmax(proba, axis=1)]

    def predict_proba(self, X):
        """Predict calibrated probabilities"""
        uncalibrated = self.base_model.predict_proba(X)
        calibrated = np.zeros_like(uncalibrated)

        # Apply isotonic calibration to each class
        for i, iso in enumerate(self.calibrators):
            calibrated[:, i] = iso.predict(uncalibrated[:, i])

        # Normalize to sum to 1
        row_sums = calibrated.sum(axis=1, keepdims=True)
        row_sums = np.maximum(row_sums, 1e-10)  # Avoid division by zero
        calibrated = calibrated / row_sums

        return calibrated


class MatchPredictor:
    """Predicts match outcomes using ensemble of models"""

    # Features to use for prediction (exclude identifiers and targets)
    FEATURE_COLS = [
        # Home team form (calculated from historical matches)
        "home_form_ppg", "home_form_goals_for", "home_form_goals_against",
        "home_form_goal_diff", "home_form_xg", "home_venue_ppg",
        "home_venue_goals_for", "home_venue_goals_against",
        "home_position", "home_season_points", "home_season_gd",

        # Away team form (calculated from historical matches)
        "away_form_ppg", "away_form_goals_for", "away_form_goals_against",
        "away_form_goal_diff", "away_form_xg", "away_venue_ppg",
        "away_venue_goals_for", "away_venue_goals_against",
        "away_position", "away_season_points", "away_season_gd",

        # Differences (calculated)
        "form_ppg_diff", "position_diff", "xg_diff",

        # League-level features
        "league_draw_rate",

        # H2H (calculated from historical matches)
        "h2h_home_wins", "h2h_draws", "h2h_away_wins", "h2h_total_goals",

        # Pre-match PPG fra FootyStats (garantert før kampen - unngår data leakage)
        "home_prematch_ppg", "away_prematch_ppg",
        "home_overall_ppg", "away_overall_ppg", "prematch_ppg_diff",

        # Pre-match xG fra FootyStats (forventet mål basert på historikk)
        "home_xg_prematch", "away_xg_prematch",
        "total_xg_prematch", "xg_prematch_diff",

        # Angrepskvalitet (ratio farlige angrep / totale angrep)
        "home_attack_quality", "away_attack_quality",

        # FootyStats potensial (ekstern modell som ensemble-input)
        "fs_btts_potential", "fs_o25_potential", "fs_o35_potential",
    ]

    def __init__(self, model_dir: Optional[Path] = None):
        self.model_dir = model_dir or Path(__file__).parent.parent.parent / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()

        # Models
        self.result_model = None  # 1X2 prediction
        self.over25_model = None  # Over 2.5 goals
        self.btts_model = None    # Both teams to score

        self.is_fitted = False

    def prepare_data(self, df: pd.DataFrame) -> Tuple[np.ndarray, dict]:
        """Prepare features and targets from DataFrame"""

        # Features
        X = df[self.FEATURE_COLS].fillna(0).values

        # Targets
        targets = {
            "result": df["target_result"].values,
            "over25": df["target_over_25"].values,
            "btts": df["target_btts"].values,
        }

        return X, targets

    def train(self, df: pd.DataFrame, test_size: float = 0.2, calibration_size: float = 0.15) -> dict:
        """
        Train all models using time-based split with proper calibration.

        Uses time-based prefit calibration to avoid overconfidence:
        1. Train base model on earliest data
        2. Calibrate on middle portion (time-based, not CV)
        3. Validate on most recent data

        Args:
            df: DataFrame with features and targets
            test_size: Fraction of data to use for validation (0.0 to use all data for training,
                       useful when you have a separate hold-out test set)
            calibration_size: Fraction of training data to use for calibration (default 0.15)
        """

        print("Preparing data...")

        # Sort by date for time-based split (critical for avoiding data leakage)
        if "date_unix" in df.columns:
            df = df.sort_values("date_unix").reset_index(drop=True)
            print(f"  Sorted {len(df)} matches by date")

        X, targets = self.prepare_data(df)

        # Encode result labels
        y_result = self.label_encoder.fit_transform(targets["result"])
        y_over25 = targets["over25"]
        y_btts = targets["btts"]

        # Time-based split with calibration set
        if test_size > 0:
            # Split: [base_train | calibration | test]
            test_idx = int(len(X) * (1 - test_size))
            cal_idx = int(test_idx * (1 - calibration_size))

            X_base_train = X[:cal_idx]
            X_calibrate = X[cal_idx:test_idx]
            X_test = X[test_idx:]

            y_res_base = y_result[:cal_idx]
            y_res_cal = y_result[cal_idx:test_idx]
            y_res_test = y_result[test_idx:]

            y_o25_base = y_over25[:cal_idx]
            y_o25_cal = y_over25[cal_idx:test_idx]
            y_o25_test = y_over25[test_idx:]

            y_btts_base = y_btts[:cal_idx]
            y_btts_cal = y_btts[cal_idx:test_idx]
            y_btts_test = y_btts[test_idx:]

            print(f"  Base train: {len(X_base_train)} matches (earliest)")
            print(f"  Calibration: {len(X_calibrate)} matches (middle)")
            print(f"  Test set: {len(X_test)} matches (most recent)")
            has_test_set = True
        else:
            # Use time-based calibration even without test set
            # Split: [base_train | calibration]
            cal_idx = int(len(X) * (1 - calibration_size))

            X_base_train = X[:cal_idx]
            X_calibrate = X[cal_idx:]

            y_res_base = y_result[:cal_idx]
            y_res_cal = y_result[cal_idx:]

            y_o25_base = y_over25[:cal_idx]
            y_o25_cal = y_over25[cal_idx:]

            y_btts_base = y_btts[:cal_idx]
            y_btts_cal = y_btts[cal_idx:]

            print(f"  Base train: {len(X_base_train)} matches (earlier)")
            print(f"  Calibration: {len(X_calibrate)} matches (later)")
            print(f"  (External hold-out assumed for testing)")
            has_test_set = False

        # Scale features
        X_base_scaled = self.scaler.fit_transform(X_base_train)
        X_cal_scaled = self.scaler.transform(X_calibrate)
        if has_test_set:
            X_test_scaled = self.scaler.transform(X_test)

        results = {}

        # === 1X2 Result Model with time-based calibration ===
        print("\nTraining 1X2 Result Model...")
        self.result_model = self._train_calibrated_model(
            X_base_scaled, y_res_base,
            X_cal_scaled, y_res_cal,
            model_type="multiclass",
            model_name="1X2"
        )

        if has_test_set:
            y_pred = self.result_model.predict(X_test_scaled)
            y_proba = self.result_model.predict_proba(X_test_scaled)
            results["result"] = {
                "accuracy": accuracy_score(y_res_test, y_pred),
                "log_loss": log_loss(y_res_test, y_proba),
                "classes": self.label_encoder.classes_.tolist()
            }
            print(f"  Accuracy: {results['result']['accuracy']:.3f}")
            print(f"  Log Loss: {results['result']['log_loss']:.3f}")
        else:
            results["result"] = {
                "accuracy": None,
                "log_loss": None,
                "classes": self.label_encoder.classes_.tolist(),
                "note": "No internal test set (external hold-out used)"
            }

        # === Over 2.5 Model ===
        print("\nTraining Over 2.5 Goals Model...")
        self.over25_model = self._train_calibrated_model(
            X_base_scaled, y_o25_base,
            X_cal_scaled, y_o25_cal,
            model_type="binary",
            model_name="Over2.5"
        )

        if has_test_set:
            y_pred = self.over25_model.predict(X_test_scaled)
            results["over25"] = {
                "accuracy": accuracy_score(y_o25_test, y_pred),
                "log_loss": log_loss(y_o25_test, self.over25_model.predict_proba(X_test_scaled)),
            }
            print(f"  Accuracy: {results['over25']['accuracy']:.3f}")
            print(f"  Log Loss: {results['over25']['log_loss']:.3f}")
        else:
            results["over25"] = {
                "accuracy": None,
                "log_loss": None,
                "note": "No internal test set (external hold-out used)"
            }

        # === BTTS Model ===
        print("\nTraining BTTS Model...")
        self.btts_model = self._train_calibrated_model(
            X_base_scaled, y_btts_base,
            X_cal_scaled, y_btts_cal,
            model_type="binary",
            model_name="BTTS"
        )

        if has_test_set:
            y_pred = self.btts_model.predict(X_test_scaled)
            results["btts"] = {
                "accuracy": accuracy_score(y_btts_test, y_pred),
                "log_loss": log_loss(y_btts_test, self.btts_model.predict_proba(X_test_scaled)),
            }
            print(f"  Accuracy: {results['btts']['accuracy']:.3f}")
            print(f"  Log Loss: {results['btts']['log_loss']:.3f}")
        else:
            results["btts"] = {
                "accuracy": None,
                "log_loss": None,
                "note": "No internal test set (external hold-out used)"
            }

        self.is_fitted = True
        return results

    def _train_calibrated_model(self, X_train, y_train, X_cal, y_cal,
                                 model_type: str = "binary", model_name: str = ""):
        """
        Train a model with time-based calibration.

        Instead of CalibratedClassifierCV(cv=3), this:
        1. Trains base model on X_train
        2. Calibrates on X_cal using isotonic regression (time-based, no CV)

        This prevents calibration from using "future" data which causes overconfidence.
        """
        # Base model configuration
        if model_type == "multiclass":
            base_model = XGBClassifier(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.1,
                random_state=42,
                eval_metric='mlogloss'
            )
        else:
            base_model = XGBClassifier(
                n_estimators=100,
                max_depth=3,
                learning_rate=0.1,
                random_state=42,
                eval_metric='logloss'
            )

        # Train base model
        base_model.fit(X_train, y_train)
        print(f"  Base model trained on {len(X_train)} samples")

        # Create calibrated wrapper with manual isotonic calibration
        calibrated = _TimeCalibratedClassifier(base_model, X_cal, y_cal)
        print(f"  Calibrated on {len(X_cal)} samples (time-based isotonic)")

        return calibrated

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """Make predictions for matches"""

        if not self.is_fitted:
            raise ValueError("Model not fitted. Call train() first.")

        X, _ = self.prepare_data(df)
        X_scaled = self.scaler.transform(X)

        # Result probabilities
        result_proba = self.result_model.predict_proba(X_scaled)
        result_classes = self.label_encoder.classes_

        # Over 2.5 probability
        over25_proba = self.over25_model.predict_proba(X_scaled)[:, 1]

        # BTTS probability
        btts_proba = self.btts_model.predict_proba(X_scaled)[:, 1]

        # Create output DataFrame
        predictions = df[["match_id", "home_team", "away_team", "game_week"]].copy()

        # Add result probabilities
        for i, cls in enumerate(result_classes):
            predictions[f"prob_{cls}"] = result_proba[:, i]

        predictions["prob_over25"] = over25_proba
        predictions["prob_btts"] = btts_proba

        # Add predicted outcome
        predictions["predicted_result"] = self.label_encoder.inverse_transform(
            result_proba.argmax(axis=1)
        )

        return predictions

    def save(self, name: str = "match_predictor"):
        """Save models to disk"""
        data = {
            "scaler": self.scaler,
            "label_encoder": self.label_encoder,
            "result_model": self.result_model,
            "over25_model": self.over25_model,
            "btts_model": self.btts_model,
        }
        path = self.model_dir / f"{name}.pkl"
        with open(path, "wb") as f:
            pickle.dump(data, f)
        print(f"Model saved to {path}")

    def load(self, name: str = "match_predictor"):
        """Load models from disk"""
        path = self.model_dir / f"{name}.pkl"
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.scaler = data["scaler"]
        self.label_encoder = data["label_encoder"]
        self.result_model = data["result_model"]
        self.over25_model = data["over25_model"]
        self.btts_model = data["btts_model"]
        self.is_fitted = True
        print(f"Model loaded from {path}")


if __name__ == "__main__":
    # Test training
    features_path = Path(__file__).parent.parent.parent / "data" / "processed" / "features.csv"
    df = pd.read_csv(features_path)

    print(f"Loaded {len(df)} matches with features")
    print()

    predictor = MatchPredictor()
    results = predictor.train(df)

    print("\n" + "=" * 50)
    print("TRAINING COMPLETE")
    print("=" * 50)

    # Save model
    predictor.save()

    # Test prediction
    print("\n=== SAMPLE PREDICTIONS ===")
    sample = df.tail(10)
    predictions = predictor.predict(sample)

    for _, row in predictions.iterrows():
        print(f"{row['home_team']} vs {row['away_team']}")
        print(f"  H: {row['prob_H']:.1%}  D: {row['prob_D']:.1%}  A: {row['prob_A']:.1%}")
        print(f"  Over 2.5: {row['prob_over25']:.1%}  BTTS: {row['prob_btts']:.1%}")
        print()
