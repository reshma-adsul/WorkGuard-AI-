"""
WorkGuard AI - Idle Detection & Auto Surveillance Module

2 features:
1. Windows boot pe auto-start (Registry method)
2. Idle detection - user 5 min se inactive hai toh full surveillance ON

Idle detection kaise kaam karta hai:
- Windows GetLastInputInfo() API use karta hai
- Last mouse/keyboard activity ka time milta hai
- Agar X minutes se koi activity nahi → IDLE state
- IDLE state mein → camera + full recording ON
- User wapas aaya → ACTIVE state → light mode
"""

import ctypes
import time
import threading
import datetime
from pathlib import Path

try:
    import winreg
    WINDOWS = True
except ImportError:
    WINDOWS = False


# ── Idle Time Detection ───────────────────────────────────────────────────────

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
    ]


def get_idle_seconds() -> float:
    """
    Returns how many seconds since last mouse/keyboard activity.
    Uses Windows GetLastInputInfo() API.
    """
    if not WINDOWS:
        return 0.0

    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))

    # GetTickCount = milliseconds since system boot
    millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
    return millis / 1000.0


# ── States ────────────────────────────────────────────────────────────────────
STATE_ACTIVE     = "ACTIVE"       # User actively using laptop
STATE_IDLE       = "IDLE"         # No activity for X minutes
STATE_AWAY       = "AWAY"         # Long idle — user clearly gone
STATE_SUSPICIOUS = "SUSPICIOUS"   # Idle then suddenly active — possible intruder


class IdleWatcher:
    """
    Monitors user idle time and switches surveillance modes automatically.

    Thresholds:
    - idle_threshold   : seconds before IDLE state (default: 5 min)
    - away_threshold   : seconds before AWAY state (default: 15 min)
    - return_threshold : seconds of activity to confirm user returned (default: 10s)
    """

    def __init__(self,
                 idle_threshold: int = 300,    # 5 minutes
                 away_threshold: int = 900,    # 15 minutes
                 on_idle=None,
                 on_away=None,
                 on_return=None,
                 on_suspicious=None,
                 camera_guard=None):

        self.idle_threshold   = idle_threshold
        self.away_threshold   = away_threshold
        self.on_idle          = on_idle
        self.on_away          = on_away
        self.on_return        = on_return
        self.on_suspicious    = on_suspicious
        self.camera_guard     = camera_guard

        self.current_state    = STATE_ACTIVE
        self.running          = False
        self._thread          = None
        self.state_log        = []

        # Stats
        self.stats = {
            "idle_count":      0,
            "away_count":      0,
            "return_count":    0,
            "suspicious_count": 0,
            "total_idle_seconds": 0,
        }

    def _log_state(self, new_state: str, idle_seconds: float):
        event = {
            "time":        datetime.datetime.now().isoformat(),
            "from":        self.current_state,
            "to":          new_state,
            "idle_secs":   round(idle_seconds, 1),
        }
        self.state_log.append(event)
        print(f"\n  ⏱️  Idle State: {self.current_state} → {new_state} (idle: {idle_seconds:.0f}s)")

    def _update_state(self, idle_seconds: float):
        """Core state machine logic"""
        old_state = self.current_state

        if idle_seconds >= self.away_threshold:
            new_state = STATE_AWAY
        elif idle_seconds >= self.idle_threshold:
            new_state = STATE_IDLE
        else:
            # User is active
            if old_state in (STATE_IDLE, STATE_AWAY):
                # Was idle, now active — suspicious?
                if old_state == STATE_AWAY:
                    new_state = STATE_SUSPICIOUS
                else:
                    new_state = STATE_ACTIVE
            else:
                new_state = STATE_ACTIVE

        if new_state == self.current_state:
            return

        self._log_state(new_state, idle_seconds)
        self.current_state = new_state

        # Fire callbacks
        if new_state == STATE_IDLE:
            self.stats["idle_count"] += 1
            print("  💤 User idle — enabling surveillance mode")
            if self.camera_guard:
                self.camera_guard.start()
            if self.on_idle:
                self.on_idle(idle_seconds)

        elif new_state == STATE_AWAY:
            self.stats["away_count"] += 1
            self.stats["total_idle_seconds"] += idle_seconds
            print("  🚪 User away — full surveillance ON")
            if self.on_away:
                self.on_away(idle_seconds)

        elif new_state == STATE_ACTIVE:
            self.stats["return_count"] += 1
            print("  ✅ User returned — normal mode")
            if self.on_return:
                self.on_return()

        elif new_state == STATE_SUSPICIOUS:
            self.stats["suspicious_count"] += 1
            print("  ⚠️  SUSPICIOUS: Was away, now suddenly active!")
            if self.on_suspicious:
                self.on_suspicious(idle_seconds)

    def _watch_loop(self):
        """Main monitoring loop"""
        print("  ⏱️  Idle watcher started")
        check_interval = 10  # Check every 10 seconds

        while self.running:
            idle_secs = get_idle_seconds()
            self._update_state(idle_secs)
            time.sleep(check_interval)

    def start(self):
        """Start idle monitoring in background thread"""
        self.running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def get_status(self) -> dict:
        return {
            "state":          self.current_state,
            "idle_seconds":   round(get_idle_seconds(), 1),
            "idle_threshold": self.idle_threshold,
            "away_threshold": self.away_threshold,
            "stats":          self.stats,
            "state_log":      self.state_log[-10:],
        }


# ── Auto-Start (Windows Registry) ────────────────────────────────────────────

REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "WorkGuardAI"

def enable_autostart(project_dir: str = None) -> dict:
    """Add WorkGuard AI to Windows startup registry"""
    import sys
    if not WINDOWS:
        return {"success": False, "error": "Windows only"}

    if project_dir is None:
        project_dir = str(Path(__file__).parent.parent)

    main_script = Path(project_dir) / "main.py"
    python_exe  = sys.executable
    pythonw     = python_exe.replace("python.exe", "pythonw.exe")

    if Path(pythonw).exists():
        cmd = f'"{pythonw}" "{main_script}" --silent'
    else:
        cmd = f'"{python_exe}" "{main_script}" --silent'

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        print(f"  ✅ Auto-start enabled!")
        return {"success": True, "command": cmd}
    except Exception as e:
        return {"success": False, "error": str(e)}


def disable_autostart() -> dict:
    """Remove WorkGuard AI from Windows startup"""
    if not WINDOWS:
        return {"success": False, "error": "Windows only"}
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
        print("  ✅ Auto-start disabled!")
        return {"success": True}
    except FileNotFoundError:
        return {"success": False, "error": "Not enabled"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def is_autostart_enabled() -> bool:
    if not WINDOWS:
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except:
        return False


# ── Convenience function for main.py ─────────────────────────────────────────

def setup_idle_watcher(idle_minutes: int = 5, away_minutes: int = 15,
                       camera_guard=None, telegram=None) -> IdleWatcher:
    """
    Create and return configured IdleWatcher.
    Call watcher.start() to begin monitoring.
    """

    def on_idle(secs):
        print(f"  💤 IDLE MODE — {secs:.0f}s inactive")

    def on_away(secs):
        print(f"  🚪 AWAY MODE — {secs:.0f}s inactive — Full surveillance")

    def on_return():
        print("  ✅ User returned to desk")

    def on_suspicious(secs):
        print(f"  ⚠️  SUSPICIOUS RETURN after {secs:.0f}s away!")
        if telegram and telegram.enabled:
            telegram.send_alert(
                "SUSPICIOUS_RETURN",
                score=0.75,
                details={"window": "IdleWatcher", "process": "system",
                         "idle_seconds": secs}
            )

    watcher = IdleWatcher(
        idle_threshold = idle_minutes * 60,
        away_threshold = away_minutes * 60,
        on_idle        = on_idle,
        on_away        = on_away,
        on_return      = on_return,
        on_suspicious  = on_suspicious,
        camera_guard   = camera_guard,
    )

    return watcher
