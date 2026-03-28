"""
WorkGuard AI - Flask REST API
Serves live data to the dashboard and exposes endpoints for session control.
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS

# Internal imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core import recorder
from ml.biometrics import KeystrokeBiometrics
from ml.anomaly import AnomalyDetector

app = Flask(__name__, static_folder="../dashboard")
CORS(app)

# Serve landing page from root folder
import os
ROOT_DIR = str(Path(__file__).parent.parent)

# ── Global state ─────────────────────────────────────────────────────────────
LOG_BASE = Path("activity_logs")
_biometrics: KeystrokeBiometrics = None
_detector:   AnomalyDetector     = None
_alert_log   = []
_session_active = False

def _get_services():
    global _biometrics, _detector
    if _biometrics is None:
        _biometrics = KeystrokeBiometrics(profile_dir=str(LOG_BASE))
    if _detector is None:
        _detector = AnomalyDetector(model_dir=str(LOG_BASE))
    return _biometrics, _detector

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def landing():
    """Landing page — first thing user sees"""
    return send_from_directory(ROOT_DIR, "landing.html")

@app.route("/dashboard")
def index():
    """Gold Luxury Dashboard"""
    import os
    dashboard_path = os.path.join(ROOT_DIR, "dashboard")
    return send_from_directory(dashboard_path, "index.html")

@app.route("/api/status")
def status():
    bio, det = _get_services()
    return jsonify({
        "session_active": _session_active,
        "session_id": recorder.session.get("id"),
        "has_biometric_profile": bio.has_profile(),
        "anomaly_model_trained": det.trained,
        "baseline_samples": det.baseline_count(),
        "server_time": datetime.now().isoformat(),
    })

@app.route("/api/live")
def live_feed():
    """Live event feed — last N events from in-memory buffer"""
    limit = int(request.args.get("limit", 50))
    events = recorder.get_buffer_snapshot()[-limit:]
    return jsonify({"events": events, "count": len(events)})

@app.route("/api/live/stream")
def live_stream():
    """Server-Sent Events (SSE) for real-time dashboard updates"""
    def generate():
        import time
        last_len = 0
        while True:
            events = recorder.get_buffer_snapshot()
            if len(events) != last_len:
                new_events = events[last_len:]
                last_len = len(events)
                data = json.dumps({"events": new_events, "total": last_len})
                yield f"data: {data}\n\n"
            time.sleep(0.5)

    return Response(generate(), content_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.route("/api/stats")
def stats():
    """Aggregated stats from current session"""
    events = recorder.get_buffer_snapshot()
    keystrokes = [e for e in events if e.get("type") == "keystroke"]
    clicks     = [e for e in events if e.get("type") == "mouse_click"]
    scrolls    = [e for e in events if e.get("type") == "mouse_scroll"]
    screenshots= [e for e in events if e.get("type") == "screenshot"]

    # Window breakdown
    window_counts = {}
    for e in keystrokes:
        w = e.get("window", "Unknown")
        window_counts[w] = window_counts.get(w, 0) + 1

    top_windows = sorted(window_counts.items(), key=lambda x: x[1], reverse=True)[:8]

    # Typing speed
    dwells = [e["dwell_ms"] for e in keystrokes if e.get("dwell_ms")]
    mean_dwell = round(sum(dwells)/len(dwells), 1) if dwells else 0

    return jsonify({
        "total_keystrokes": len(keystrokes),
        "total_clicks": len(clicks),
        "total_scrolls": len(scrolls),
        "total_screenshots": len(screenshots),
        "top_windows": top_windows,
        "mean_dwell_ms": mean_dwell,
        "alerts": _alert_log[-10:],
    })

@app.route("/api/biometric/score")
def biometric_score():
    """Real-time biometric similarity score"""
    bio, _ = _get_services()
    events  = recorder.get_buffer_snapshot()
    result  = bio.compute_similarity_score(events)
    return jsonify(result)

@app.route("/api/anomaly/score")
def anomaly_score():
    """Real-time anomaly score"""
    _, det  = _get_services()
    events  = recorder.get_buffer_snapshot()
    result  = det.predict(events)

    # If anomaly detected, log it
    if result.get("anomaly") and result.get("score", 0) > 0.6:
        _alert_log.append({
            "time": datetime.now().isoformat(),
            "type": "anomaly",
            "score": result["score"],
            "types": result.get("anomaly_types", []),
        })

    return jsonify(result)

@app.route("/api/calibrate", methods=["POST"])
def calibrate():
    """Add current session events to baseline (call when real user is typing)"""
    _, det = _get_services()
    bio, _ = _get_services()
    events  = recorder.get_buffer_snapshot()

    det.add_baseline_sample(events)
    profile = bio.build_profile(events)

    return jsonify({
        "success": True,
        "profile": profile,
        "baseline_samples": det.baseline_count(),
    })

@app.route("/api/sessions")
def list_sessions():
    """List all recorded sessions"""
    sessions = []
    if LOG_BASE.exists():
        for d in sorted(LOG_BASE.iterdir(), reverse=True):
            if d.is_dir():
                meta_file = d / "session_meta.json"
                meta = {}
                if meta_file.exists():
                    with open(meta_file) as f:
                        meta = json.load(f)
                event_file = d / "events.jsonl"
                event_count = 0
                if event_file.exists():
                    with open(event_file) as f:
                        event_count = sum(1 for _ in f)
                sessions.append({
                    "id": d.name,
                    "meta": meta,
                    "event_count": event_count,
                    "has_report": (d / "report.html").exists(),
                })
    return jsonify({"sessions": sessions[:20]})

@app.route("/api/sessions/<session_id>/events")
def session_events(session_id):
    """Events from a past session"""
    event_file = LOG_BASE / session_id / "events.jsonl"
    if not event_file.exists():
        return jsonify({"error": "Session not found"}), 404
    events = []
    with open(event_file) as f:
        for line in f:
            try: events.append(json.loads(line))
            except: pass
    return jsonify({"events": events[-500:], "total": len(events)})

@app.route("/api/alerts")
def get_alerts():
    return jsonify({"alerts": _alert_log})


def run_api(host="127.0.0.1", port=5000, debug=False):
    """Start Flask in a background thread"""
    thread = threading.Thread(
        target=lambda: app.run(host=host, port=port, debug=debug, use_reloader=False),
        daemon=True
    )
    thread.start()
    print(f"🌐 Dashboard API: http://{host}:{port}")
    return thread


if __name__ == "__main__":
    app.run(debug=True, port=5000)

@app.route("/api/camera/status")
def camera_status():
    """Camera guard ka current status"""
    try:
        import main as m
        if m.camera_guard:
            return jsonify(m.camera_guard.get_status())
    except Exception:
        pass
    return jsonify({"state": "DISABLED", "has_profile": False})

@app.route("/api/camera/register", methods=["POST"])
def camera_register():
    """Register owner face"""
    try:
        import main as m
        if m.camera_guard:
            result = m.camera_guard.register_owner(num_samples=8)
            return jsonify(result)
    except Exception as e:
        pass
    return jsonify({"success": False, "error": "Camera not available"})

# ── Database API endpoints ────────────────────────────────────────────────────
@app.route("/api/db/stats")
def db_stats():
    """Session stats from SQLite database"""
    try:
        from database.db import WorkGuardDB
        session_id = recorder.session.get("id")
        if not session_id:
            return jsonify({"error": "No active session"})
        db_path = LOG_BASE / session_id / "workguard.db"
        if not db_path.exists():
            return jsonify({"error": "Database not found"})
        db   = WorkGuardDB(str(db_path))
        data = db.get_dashboard_stats(session_id)
        db.close()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/db/alerts")
def db_alerts():
    """All alerts from database"""
    try:
        from database.db import WorkGuardDB
        session_id = recorder.session.get("id")
        if not session_id:
            return jsonify({"alerts": []})
        db_path = LOG_BASE / session_id / "workguard.db"
        if not db_path.exists():
            return jsonify({"alerts": []})
        db      = WorkGuardDB(str(db_path))
        alerts  = db.get_alerts(session_id)
        db.close()
        return jsonify({"alerts": alerts})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/db/windows")
def db_windows():
    """Window usage stats from database"""
    try:
        from database.db import WorkGuardDB
        session_id = recorder.session.get("id")
        if not session_id:
            return jsonify({"windows": []})
        db_path = LOG_BASE / session_id / "workguard.db"
        if not db_path.exists():
            return jsonify({"windows": []})
        db      = WorkGuardDB(str(db_path))
        windows = db.get_window_stats(session_id)
        db.close()
        return jsonify({"windows": windows})
    except Exception as e:
        return jsonify({"error": str(e)})
