"""
WorkGuard AI - Anomaly Detection Engine
Uses Isolation Forest (unsupervised ML) to detect unusual activity patterns.

Why Isolation Forest?
- Works without labeled data (no need to pre-define "bad" behavior)
- Efficient on high-dimensional behavioral data
- Industry standard for unsupervised anomaly detection
"""

import json
import math
import statistics
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import List, Dict, Optional

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    import numpy as np
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False


# ── Feature Engineering ──────────────────────────────────────────────────────

def extract_features(events: List[dict], window_seconds: int = 60) -> Optional[Dict]:
    """
    Extract behavioral features from a window of events.
    These features form the input vector to the ML model.
    """
    now = datetime.now()
    keystrokes    = [e for e in events if e.get("type") == "keystroke"]
    clicks        = [e for e in events if e.get("type") == "mouse_click"]
    scrolls       = [e for e in events if e.get("type") == "mouse_scroll"]

    if len(keystrokes) < 3:
        return None

    # Feature 1: Typing speed (keystrokes per minute)
    kpm = len(keystrokes) / (window_seconds / 60)

    # Feature 2: Mean dwell time
    dwells = [e["dwell_ms"] for e in keystrokes if e.get("dwell_ms")]
    mean_dwell = statistics.mean(dwells) if dwells else 0

    # Feature 3: Mean flight time
    flights = [e["flight_ms"] for e in keystrokes if e.get("flight_ms")]
    mean_flight = statistics.mean(flights) if flights else 0

    # Feature 4: Dwell variance (consistency)
    dwell_var = statistics.stdev(dwells) if len(dwells) > 1 else 0

    # Feature 5: Mouse click rate
    click_rate = len(clicks) / (window_seconds / 60)

    # Feature 6: Scroll rate
    scroll_rate = len(scrolls) / (window_seconds / 60)

    # Feature 7: Hour of day (unusual time?)
    hour = now.hour

    # Feature 8: Special key ratio (Ctrl, Alt, Win combos - hackers use these more)
    special = [e for e in keystrokes if e.get("key","").startswith("[") and
               e.get("key") not in ("[SPACE]","[ENTER]","[BACKSPACE]","[TAB]")]
    special_ratio = len(special) / max(len(keystrokes), 1)

    # Feature 9: Unique windows count (jumping between apps)
    windows = set(e.get("window","") for e in events)
    unique_windows = len(windows)

    return {
        "kpm": round(kpm, 2),
        "mean_dwell": round(mean_dwell, 2),
        "mean_flight": round(mean_flight, 2),
        "dwell_var": round(dwell_var, 2),
        "click_rate": round(click_rate, 2),
        "scroll_rate": round(scroll_rate, 2),
        "hour": hour,
        "special_ratio": round(special_ratio, 4),
        "unique_windows": unique_windows,
    }


def features_to_vector(f: dict) -> list:
    return [
        f["kpm"], f["mean_dwell"], f["mean_flight"], f["dwell_var"],
        f["click_rate"], f["scroll_rate"], f["hour"],
        f["special_ratio"], f["unique_windows"]
    ]


# ── Model ────────────────────────────────────────────────────────────────────

class AnomalyDetector:
    """
    Isolation Forest based anomaly detector.
    Train on the original user's behavior, then detect deviations.
    """

    MODEL_FILE = "anomaly_model.json"  # We serialize manually (no joblib dependency)

    def __init__(self, model_dir: str = "."):
        self.model_dir  = Path(model_dir)
        self.model      = None
        self.scaler     = None
        self.trained    = False
        self.baseline   = []   # Historical feature vectors for normalization
        self._load_model()

    def _load_model(self):
        model_path = self.model_dir / self.MODEL_FILE
        if model_path.exists():
            with open(model_path) as f:
                data = json.load(f)
            self.baseline = data.get("baseline", [])
            self.trained  = len(self.baseline) >= 10
            if SKLEARN_OK and self.trained:
                self._fit_model()

    def _save_model(self):
        self.model_dir.mkdir(parents=True, exist_ok=True)
        with open(self.model_dir / self.MODEL_FILE, "w") as f:
            json.dump({"baseline": self.baseline, "trained_at": datetime.now().isoformat()}, f)

    def _fit_model(self):
        """Fit IsolationForest on stored baseline"""
        if not SKLEARN_OK or len(self.baseline) < 5:
            return
        X = np.array(self.baseline)
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        self.model = IsolationForest(
            n_estimators=100,
            contamination=0.05,  # Expect 5% anomalies
            random_state=42
        )
        self.model.fit(X_scaled)
        self.trained = True

    def add_baseline_sample(self, events: list, window_seconds: int = 60):
        """Add a normal behavior sample to baseline"""
        features = extract_features(events, window_seconds)
        if not features:
            return False
        self.baseline.append(features_to_vector(features))
        if len(self.baseline) >= 10:
            self._fit_model()
        self._save_model()
        return True

    def predict(self, events: list, window_seconds: int = 60) -> dict:
        """
        Predict if current behavior is anomalous.
        Returns anomaly score and classification.
        """
        features = extract_features(events, window_seconds)
        if not features:
            return {"anomaly": False, "score": 0.0, "reason": "insufficient_data"}

        if not self.trained or not SKLEARN_OK:
            # Fallback: simple rule-based detection
            return self._rule_based_detect(features)

        vec = np.array([features_to_vector(features)])
        vec_scaled = self.scaler.transform(vec)

        # IsolationForest: -1 = anomaly, 1 = normal
        prediction = self.model.predict(vec_scaled)[0]
        # Raw score: more negative = more anomalous
        raw_score  = self.model.score_samples(vec_scaled)[0]
        # Normalize to 0-1 (higher = more anomalous)
        anomaly_score = max(0, min(1, (-raw_score - 0.3) * 2))

        anomaly_types = []
        if features["hour"] < 6 or features["hour"] > 22:
            anomaly_types.append("unusual_time")
        if features["special_ratio"] > 0.3:
            anomaly_types.append("excessive_shortcuts")
        if features["unique_windows"] > 8:
            anomaly_types.append("suspicious_app_hopping")

        return {
            "anomaly": prediction == -1,
            "score": round(anomaly_score, 4),
            "anomaly_types": anomaly_types,
            "features": features,
            "model": "IsolationForest",
        }

    def _rule_based_detect(self, features: dict) -> dict:
        """Fallback when sklearn not available or not enough training data"""
        flags = []
        score = 0.0

        if features["hour"] < 6 or features["hour"] > 22:
            flags.append("unusual_time"); score += 0.3
        if features["kpm"] > 300:
            flags.append("superhuman_typing_speed"); score += 0.4
        if features["special_ratio"] > 0.4:
            flags.append("excessive_special_keys"); score += 0.25
        if features["mean_dwell"] < 20:
            flags.append("suspiciously_fast_keypress"); score += 0.3
        if features["unique_windows"] > 10:
            flags.append("excessive_app_switching"); score += 0.2

        return {
            "anomaly": score >= 0.4,
            "score": round(min(score, 1.0), 4),
            "anomaly_types": flags,
            "features": features,
            "model": "rule_based",
        }

    def baseline_count(self) -> int:
        return len(self.baseline)
