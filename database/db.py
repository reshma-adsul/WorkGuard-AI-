"""
WorkGuard AI - SQLite Database Module
Stores all events, sessions, alerts in a proper database.

Why SQLite?
- Built into Python (no install needed)
- Single file database
- SQL queries — filter by time, type, window etc.
- Resume mein: "Designed SQLite schema for behavioral event storage"
"""

import sqlite3
import json
import datetime
from pathlib import Path
from typing import List, Optional


class WorkGuardDB:
    """
    SQLite database for WorkGuard AI.
    
    Tables:
    - sessions     → each recording session
    - events       → all keyboard/mouse/screenshot events
    - alerts       → detected anomalies and threats
    - biometric_profiles → user typing fingerprints
    - camera_events → camera state changes
    """

    def __init__(self, db_path: str = "workguard.db"):
        self.db_path = db_path
        self.conn    = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Dict-like rows
        self._create_tables()
        print(f"  💾 Database: {db_path}")

    # ── Schema ────────────────────────────────────────────────────────────────
    def _create_tables(self):
        cursor = self.conn.cursor()

        cursor.executescript("""
        -- Sessions table
        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT PRIMARY KEY,
            start_time  TEXT NOT NULL,
            end_time    TEXT,
            username    TEXT,
            hostname    TEXT,
            encrypted   INTEGER DEFAULT 0,
            screenshot_interval INTEGER DEFAULT 30,
            total_events INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        -- Events table (keyboard, mouse, screenshots)
        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT NOT NULL,
            time        TEXT NOT NULL,
            type        TEXT NOT NULL,
            key         TEXT,
            button      TEXT,
            x           INTEGER,
            y           INTEGER,
            direction   TEXT,
            window      TEXT,
            process     TEXT,
            dwell_ms    INTEGER,
            flight_ms   INTEGER,
            file        TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        -- Alerts table
        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT,
            time        TEXT NOT NULL,
            type        TEXT NOT NULL,
            score       REAL,
            details     TEXT,
            screenshot  TEXT,
            resolved    INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        -- Biometric profiles
        CREATE TABLE IF NOT EXISTS biometric_profiles (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT NOT NULL,
            dwell_mean   REAL,
            dwell_std    REAL,
            flight_mean  REAL,
            flight_std   REAL,
            avg_wpm      REAL,
            sample_size  INTEGER,
            created_at   TEXT DEFAULT (datetime('now')),
            updated_at   TEXT DEFAULT (datetime('now'))
        );

        -- Camera events
        CREATE TABLE IF NOT EXISTS camera_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT,
            time        TEXT NOT NULL,
            from_state  TEXT,
            to_state    TEXT,
            photo_file  TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        -- Indexes for fast queries
        CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
        CREATE INDEX IF NOT EXISTS idx_events_type    ON events(type);
        CREATE INDEX IF NOT EXISTS idx_events_time    ON events(time);
        CREATE INDEX IF NOT EXISTS idx_alerts_session ON alerts(session_id);
        CREATE INDEX IF NOT EXISTS idx_alerts_score   ON alerts(score);
        """)

        self.conn.commit()

    # ── Session methods ───────────────────────────────────────────────────────
    def create_session(self, session_id: str, meta: dict) -> bool:
        try:
            self.conn.execute("""
                INSERT INTO sessions (id, start_time, username, hostname, encrypted, screenshot_interval)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                meta.get("start_time", datetime.datetime.now().isoformat()),
                meta.get("computer_user", "Unknown"),
                meta.get("hostname", "Unknown"),
                1 if meta.get("encrypted") else 0,
                meta.get("screenshot_interval", 30),
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"  [DB] Session create failed: {e}")
            return False

    def end_session(self, session_id: str) -> bool:
        try:
            # Count total events
            count = self.conn.execute(
                "SELECT COUNT(*) FROM events WHERE session_id = ?", (session_id,)
            ).fetchone()[0]

            self.conn.execute("""
                UPDATE sessions SET end_time = ?, total_events = ? WHERE id = ?
            """, (datetime.datetime.now().isoformat(), count, session_id))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"  [DB] Session end failed: {e}")
            return False

    def get_sessions(self, limit: int = 20) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM sessions ORDER BY start_time DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Event methods ─────────────────────────────────────────────────────────
    def insert_event(self, session_id: str, event: dict) -> bool:
        try:
            self.conn.execute("""
                INSERT INTO events
                (session_id, time, type, key, button, x, y, direction, window, process, dwell_ms, flight_ms, file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                event.get("time"),
                event.get("type"),
                event.get("key"),
                event.get("button"),
                event.get("x"),
                event.get("y"),
                event.get("direction"),
                event.get("window"),
                event.get("process"),
                event.get("dwell_ms"),
                event.get("flight_ms"),
                event.get("file"),
            ))
            return True
        except Exception as e:
            return False

    def bulk_insert_events(self, session_id: str, events: List[dict]) -> int:
        """Insert multiple events at once — faster than one by one"""
        inserted = 0
        try:
            data = [(
                session_id,
                e.get("time"), e.get("type"), e.get("key"),
                e.get("button"), e.get("x"), e.get("y"),
                e.get("direction"), e.get("window"), e.get("process"),
                e.get("dwell_ms"), e.get("flight_ms"), e.get("file"),
            ) for e in events]

            self.conn.executemany("""
                INSERT INTO events
                (session_id, time, type, key, button, x, y, direction, window, process, dwell_ms, flight_ms, file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)
            self.conn.commit()
            inserted = len(data)
        except Exception as e:
            print(f"  [DB] Bulk insert failed: {e}")
        return inserted

    def get_events(self, session_id: str, event_type: str = None,
                   limit: int = 500) -> List[dict]:
        if event_type:
            rows = self.conn.execute("""
                SELECT * FROM events WHERE session_id = ? AND type = ?
                ORDER BY time DESC LIMIT ?
            """, (session_id, event_type, limit)).fetchall()
        else:
            rows = self.conn.execute("""
                SELECT * FROM events WHERE session_id = ?
                ORDER BY time DESC LIMIT ?
            """, (session_id, limit)).fetchall()
        return [dict(r) for r in rows]

    def get_keystroke_stats(self, session_id: str) -> dict:
        """Aggregate keystroke statistics for a session"""
        row = self.conn.execute("""
            SELECT
                COUNT(*) as total_keys,
                AVG(dwell_ms) as avg_dwell,
                AVG(flight_ms) as avg_flight,
                MIN(time) as first_key,
                MAX(time) as last_key
            FROM events
            WHERE session_id = ? AND type = 'keystroke'
        """, (session_id,)).fetchone()
        return dict(row) if row else {}

    def get_window_stats(self, session_id: str) -> List[dict]:
        """Get keystroke count per window/app"""
        rows = self.conn.execute("""
            SELECT window, process, COUNT(*) as keystrokes
            FROM events
            WHERE session_id = ? AND type = 'keystroke'
            GROUP BY window
            ORDER BY keystrokes DESC
            LIMIT 10
        """, (session_id,)).fetchall()
        return [dict(r) for r in rows]

    # ── Alert methods ─────────────────────────────────────────────────────────
    def insert_alert(self, session_id: str, alert_type: str,
                     score: float, details: dict = None, screenshot: str = None) -> int:
        try:
            cursor = self.conn.execute("""
                INSERT INTO alerts (session_id, time, type, score, details, screenshot)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                datetime.datetime.now().isoformat(),
                alert_type,
                score,
                json.dumps(details or {}),
                screenshot,
            ))
            self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"  [DB] Alert insert failed: {e}")
            return -1

    def get_alerts(self, session_id: str = None, min_score: float = 0.0) -> List[dict]:
        if session_id:
            rows = self.conn.execute("""
                SELECT * FROM alerts WHERE session_id = ? AND score >= ?
                ORDER BY time DESC
            """, (session_id, min_score)).fetchall()
        else:
            rows = self.conn.execute("""
                SELECT * FROM alerts WHERE score >= ?
                ORDER BY time DESC LIMIT 50
            """, (min_score,)).fetchall()
        return [dict(r) for r in rows]

    # ── Biometric methods ─────────────────────────────────────────────────────
    def save_biometric_profile(self, username: str, profile: dict) -> bool:
        try:
            existing = self.conn.execute(
                "SELECT id FROM biometric_profiles WHERE username = ?", (username,)
            ).fetchone()

            if existing:
                self.conn.execute("""
                    UPDATE biometric_profiles
                    SET dwell_mean=?, dwell_std=?, flight_mean=?, flight_std=?,
                        avg_wpm=?, sample_size=?, updated_at=datetime('now')
                    WHERE username=?
                """, (
                    profile.get("dwell_mean"), profile.get("dwell_std"),
                    profile.get("flight_mean"), profile.get("flight_std"),
                    profile.get("avg_wpm"), profile.get("sample_size"),
                    username,
                ))
            else:
                self.conn.execute("""
                    INSERT INTO biometric_profiles
                    (username, dwell_mean, dwell_std, flight_mean, flight_std, avg_wpm, sample_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    username,
                    profile.get("dwell_mean"), profile.get("dwell_std"),
                    profile.get("flight_mean"), profile.get("flight_std"),
                    profile.get("avg_wpm"), profile.get("sample_size"),
                ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"  [DB] Profile save failed: {e}")
            return False

    def get_biometric_profile(self, username: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM biometric_profiles WHERE username = ?", (username,)
        ).fetchone()
        return dict(row) if row else None

    # ── Camera methods ────────────────────────────────────────────────────────
    def insert_camera_event(self, session_id: str, from_state: str,
                            to_state: str, photo_file: str = None) -> bool:
        try:
            self.conn.execute("""
                INSERT INTO camera_events (session_id, time, from_state, to_state, photo_file)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session_id,
                datetime.datetime.now().isoformat(),
                from_state, to_state, photo_file,
            ))
            self.conn.commit()
            return True
        except Exception as e:
            return False

    # ── Analytics queries ─────────────────────────────────────────────────────
    def get_dashboard_stats(self, session_id: str) -> dict:
        """All stats needed for dashboard in one query"""
        events = self.conn.execute("""
            SELECT type, COUNT(*) as count FROM events
            WHERE session_id = ? GROUP BY type
        """, (session_id,)).fetchall()

        counts = {row["type"]: row["count"] for row in events}

        alerts = self.conn.execute("""
            SELECT COUNT(*) as total, MAX(score) as max_score
            FROM alerts WHERE session_id = ?
        """, (session_id,)).fetchone()

        return {
            "keystrokes":   counts.get("keystroke", 0),
            "clicks":       counts.get("mouse_click", 0),
            "scrolls":      counts.get("mouse_scroll", 0),
            "screenshots":  counts.get("screenshot", 0),
            "total_alerts": dict(alerts)["total"] if alerts else 0,
            "max_threat":   dict(alerts)["max_score"] if alerts else 0,
            "window_stats": self.get_window_stats(session_id),
            "keystroke_stats": self.get_keystroke_stats(session_id),
        }

    def close(self):
        self.conn.close()
