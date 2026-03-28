"""
WorkGuard AI - One-Class SVM Anomaly Detector
Alternative to Isolation Forest — better for small datasets.

One-Class SVM learns a tight boundary around normal behavior.
Anything outside = anomaly.

When to use which:
- Isolation Forest → large datasets, fast training
- One-Class SVM   → small datasets, more precise boundary
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime

try:
    from sklearn.svm import OneClassSVM
    from sklearn.preprocessing import StandardScaler
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

# Reuse feature extraction from anomaly.py
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from ml.anomaly import extract_features, features_to_vector


class SVMAnomalyDetector:
    """
    One-Class SVM based anomaly detector.
    More precise than Isolation Forest for small datasets.
    Kernel: RBF (Radial Basis Function) — handles non-linear patterns.
    """

    MODEL_FILE = "svm_model.json"

    def __init__(self, model_dir: str = "."):
        self.model_dir = Path(model_dir)
        self.model     = None
        self.scaler    = None
        self.baseline  = []
        self.trained   = False
        self._load()

    def _load(self):
        path = self.model_dir / self.MODEL_FILE
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            self.baseline = data.get("baseline", [])
            self.trained  = len(self.baseline) >= 5
            if SKLEARN_OK and self.trained:
                self._fit()

    def _save(self):
        self.model_dir.mkdir(parents=True, exist_ok=True)
        with open(self.model_dir / self.MODEL_FILE, "w") as f:
            json.dump({"baseline": self.baseline, "trained_at": datetime.now().isoformat()}, f)

    def _fit(self):
        if not SKLEARN_OK or len(self.baseline) < 3:
            return
        X = np.array(self.baseline)
        self.scaler = StandardScaler()
        X_scaled    = self.scaler.fit_transform(X)

        # nu = upper bound on fraction of outliers (5%)
        # gamma = 'scale' — automatically set based on features
        self.model = OneClassSVM(kernel="rbf", nu=0.05, gamma="scale")
        self.model.fit(X_scaled)
        self.trained = True

    def add_baseline(self, events: list, window_seconds: int = 60) -> bool:
        features = extract_features(events, window_seconds)
        if not features:
            return False
        self.baseline.append(features_to_vector(features))
        if len(self.baseline) >= 5:
            self._fit()
        self._save()
        return True

    def predict(self, events: list, window_seconds: int = 60) -> dict:
        features = extract_features(events, window_seconds)
        if not features:
            return {"anomaly": False, "score": 0.0, "model": "svm", "reason": "insufficient_data"}

        if not self.trained or not SKLEARN_OK:
            return {"anomaly": False, "score": 0.0, "model": "svm", "reason": "not_trained"}

        vec       = np.array([features_to_vector(features)])
        vec_scaled = self.scaler.transform(vec)

        # 1 = normal, -1 = anomaly
        prediction    = self.model.predict(vec_scaled)[0]
        # Decision function: negative = more anomalous
        decision_score = self.model.decision_function(vec_scaled)[0]
        # Normalize to 0-1
        anomaly_score  = max(0, min(1, (-decision_score + 0.5)))

        return {
            "anomaly":  prediction == -1,
            "score":    round(anomaly_score, 4),
            "model":    "OneClassSVM_RBF",
            "features": features,
            "baseline_samples": len(self.baseline),
        }

    def compare_with_isolation_forest(self, events: list) -> dict:
        """
        Run both models and return combined result.
        Ensemble approach — more reliable than single model.
        """
        from ml.anomaly import AnomalyDetector
        iso = AnomalyDetector(model_dir=str(self.model_dir))

        svm_result = self.predict(events)
        iso_result = iso.predict(events)

        # Ensemble: average scores
        svm_score = svm_result.get("score", 0)
        iso_score = iso_result.get("score", 0)
        avg_score = (svm_score + iso_score) / 2

        # Unanimous vote: both must agree for high confidence
        both_anomaly = svm_result.get("anomaly") and iso_result.get("anomaly")

        return {
            "anomaly":       both_anomaly,
            "ensemble_score": round(avg_score, 4),
            "svm_score":     svm_score,
            "iso_score":     iso_score,
            "confidence":    "high" if both_anomaly else "low",
            "model":         "Ensemble (SVM + IsolationForest)",
        }

    def baseline_count(self) -> int:
        return len(self.baseline)
