"""
WorkGuard AI - Keystroke Dynamics Biometrics
Builds a typing fingerprint for the original user.
Compares against unknown user's typing pattern.

Research basis: Keystroke dynamics is a behavioral biometric used in
academic literature (CMU Keystroke Dataset) and industry products.
"""

import json
import math
import statistics
from pathlib import Path
from typing import Optional


class KeystrokeBiometrics:
    """
    Typing fingerprint based on:
    - Mean dwell time (how long each key is held)
    - Mean flight time (time between consecutive keys)
    - Typing speed (WPM)
    - Dwell/flight variance (consistency of typing)
    """

    PROFILE_FILE = "user_typing_profile.json"

    def __init__(self, profile_dir: str = "."):
        self.profile_path = Path(profile_dir) / self.PROFILE_FILE
        self.profile: Optional[dict] = None
        self._load_profile()

    # ── Profile management ───────────────────────────────────────────────────
    def _load_profile(self):
        if self.profile_path.exists():
            with open(self.profile_path) as f:
                self.profile = json.load(f)

    def has_profile(self) -> bool:
        return self.profile is not None

    def build_profile(self, events: list) -> dict:
        """
        Build user profile from a list of keystroke events.
        Call this during a 'calibration' session with the real user.
        Needs at least 50 keystrokes for reliability.
        """
        dwell_times  = [e["dwell_ms"]  for e in events if e.get("type") == "keystroke" and e.get("dwell_ms")]
        flight_times = [e["flight_ms"] for e in events if e.get("type") == "keystroke" and e.get("flight_ms")]

        if len(dwell_times) < 20:
            return {"error": "Not enough keystrokes for profiling (need 50+)"}

        # WPM: count SPACE + ENTER as word boundaries
        word_keys = [e for e in events if e.get("type") == "keystroke"
                     and e.get("key") in ("[SPACE]", "[ENTER]")]

        profile = {
            "dwell_mean":    round(statistics.mean(dwell_times), 2),
            "dwell_std":     round(statistics.stdev(dwell_times) if len(dwell_times) > 1 else 0, 2),
            "flight_mean":   round(statistics.mean(flight_times), 2) if flight_times else 0,
            "flight_std":    round(statistics.stdev(flight_times) if len(flight_times) > 1 else 0, 2),
            "avg_wpm":       self._estimate_wpm(events),
            "sample_size":   len(dwell_times),
            "calibrated_at": __import__("datetime").datetime.now().isoformat(),
        }

        with open(self.profile_path, "w") as f:
            json.dump(profile, f, indent=2)

        self.profile = profile
        return profile

    def _estimate_wpm(self, events: list) -> float:
        """Estimate words per minute from keystroke events"""
        keystrokes = [e for e in events if e.get("type") == "keystroke"]
        if len(keystrokes) < 2:
            return 0.0
        try:
            from datetime import datetime
            t0 = datetime.fromisoformat(keystrokes[0]["time"])
            t1 = datetime.fromisoformat(keystrokes[-1]["time"])
            minutes = (t1 - t0).total_seconds() / 60
            if minutes <= 0:
                return 0.0
            chars = len(keystrokes)
            wpm = (chars / 5) / minutes  # standard: 5 chars = 1 word
            return round(wpm, 1)
        except Exception:
            return 0.0

    # ── Scoring ──────────────────────────────────────────────────────────────
    def compute_similarity_score(self, events: list) -> dict:
        """
        Compare current session's typing against stored profile.
        Returns score 0.0 (completely different) to 1.0 (identical pattern).
        """
        if not self.profile:
            return {"score": None, "reason": "No profile found. Run calibration first."}

        dwell_times  = [e["dwell_ms"]  for e in events if e.get("type") == "keystroke" and e.get("dwell_ms")]
        flight_times = [e["flight_ms"] for e in events if e.get("type") == "keystroke" and e.get("flight_ms")]

        if len(dwell_times) < 10:
            return {"score": None, "reason": "Not enough keystrokes yet (need 10+)"}

        cur_dwell_mean  = statistics.mean(dwell_times)
        cur_flight_mean = statistics.mean(flight_times) if flight_times else self.profile["flight_mean"]
        cur_wpm         = self._estimate_wpm(events)

        # Z-score based distance for each feature
        scores = []

        def zscore_sim(cur, mean, std, weight=1.0):
            if std == 0: std = 1
            z = abs(cur - mean) / std
            # Convert z-score to similarity: z=0 → 1.0, z=3 → ~0.05
            sim = math.exp(-0.5 * z)
            return sim * weight

        scores.append(zscore_sim(cur_dwell_mean,  self.profile["dwell_mean"],  self.profile["dwell_std"],  weight=0.4))
        scores.append(zscore_sim(cur_flight_mean, self.profile["flight_mean"], self.profile["flight_std"], weight=0.4))

        if self.profile["avg_wpm"] > 0 and cur_wpm > 0:
            scores.append(zscore_sim(cur_wpm, self.profile["avg_wpm"], max(self.profile["avg_wpm"] * 0.3, 5), weight=0.2))

        total_weight = 0.4 + 0.4 + (0.2 if self.profile["avg_wpm"] > 0 else 0)
        final_score  = sum(scores) / total_weight if total_weight > 0 else 0

        return {
            "score": round(final_score, 4),
            "is_original_user": final_score >= 0.65,
            "confidence": "high" if len(dwell_times) > 50 else "low",
            "details": {
                "current_dwell_ms": round(cur_dwell_mean, 2),
                "profile_dwell_ms": self.profile["dwell_mean"],
                "current_flight_ms": round(cur_flight_mean, 2),
                "profile_flight_ms": self.profile["flight_mean"],
                "current_wpm": cur_wpm,
                "profile_wpm": self.profile["avg_wpm"],
                "sample_size": len(dwell_times),
            }
        }
