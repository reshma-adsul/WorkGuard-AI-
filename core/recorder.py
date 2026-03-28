"""
WorkGuard AI - Core Recorder Module
Silently captures keyboard, mouse, screenshots, active window
"""

import os
import json
import time
import threading
import datetime
from pathlib import Path
from pynput import keyboard, mouse
from PIL import ImageGrab

try:
    import win32gui, win32process, psutil
    PLATFORM = "windows"
except ImportError:
    PLATFORM = "other"

# ── Shared session state (set by main app) ──────────────────────────────────
session = {
    "id": None,
    "log_dir": None,
    "running": False,
    "screenshot_interval": 30,
}

# ── In-memory event buffer (flushed to disk every 5s) ───────────────────────
_event_buffer = []
_buffer_lock  = threading.Lock()

SPECIAL_KEYS = {
    'Key.space':'[SPACE]','Key.enter':'[ENTER]','Key.backspace':'[BACKSPACE]',
    'Key.delete':'[DELETE]','Key.tab':'[TAB]','Key.shift':'[SHIFT]',
    'Key.ctrl_l':'[CTRL]','Key.ctrl_r':'[CTRL]','Key.alt_l':'[ALT]',
    'Key.alt_r':'[ALT]','Key.caps_lock':'[CAPS]','Key.esc':'[ESC]',
    'Key.up':'[↑]','Key.down':'[↓]','Key.left':'[←]','Key.right':'[→]',
    'Key.cmd':'[WIN]','Key.f1':'[F1]','Key.f2':'[F2]','Key.f3':'[F3]',
    'Key.f4':'[F4]','Key.f5':'[F5]','Key.f6':'[F6]','Key.f7':'[F7]',
    'Key.f8':'[F8]','Key.f9':'[F9]','Key.f10':'[F10]','Key.f11':'[F11]',
    'Key.f12':'[F12]',
}

def _ts():
    return datetime.datetime.now().isoformat(timespec='milliseconds')

def _fmt_key(key):
    s = str(key)
    if s in SPECIAL_KEYS: return SPECIAL_KEYS[s]
    if s.startswith("'") and s.endswith("'"): return s[1:-1]
    return f'[{s}]'

def _get_window():
    if PLATFORM == "windows":
        try:
            hwnd  = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc  = psutil.Process(pid).name()
            return {"title": title, "process": proc}
        except: pass
    return {"title": "Unknown", "process": "Unknown"}

def _push(event: dict):
    """Push event to buffer"""
    with _buffer_lock:
        _event_buffer.append(event)

# ── Keystroke timing for biometrics ─────────────────────────────────────────
_last_key_time = None

def on_key_press(key):
    global _last_key_time
    now = time.time()
    dwell_start = now

    flight_time = round(now - _last_key_time, 4) if _last_key_time else None
    _last_key_time = now

    win = _get_window()
    _push({
        "type": "keystroke",
        "time": _ts(),
        "key": _fmt_key(key),
        "window": win["title"],
        "process": win["process"],
        "flight_ms": int(flight_time * 1000) if flight_time else None,
        "dwell_start": dwell_start,
    })

def on_key_release(key):
    """Calculate dwell time"""
    now = time.time()
    with _buffer_lock:
        # Find last keystroke event and add dwell
        for ev in reversed(_event_buffer):
            if ev.get("type") == "keystroke" and "dwell_start" in ev:
                ev["dwell_ms"] = int((now - ev.pop("dwell_start")) * 1000)
                break

# ── Mouse ────────────────────────────────────────────────────────────────────
_last_move_ts = 0

def on_click(x, y, button, pressed):
    if not pressed: return
    win = _get_window()
    _push({
        "type": "mouse_click",
        "time": _ts(),
        "button": str(button).replace("Button.", ""),
        "x": x, "y": y,
        "window": win["title"],
        "process": win["process"],
    })

def on_scroll(x, y, dx, dy):
    _push({
        "type": "mouse_scroll",
        "time": _ts(),
        "direction": "up" if dy > 0 else "down",
        "x": x, "y": y,
    })

def on_move(x, y):
    global _last_move_ts
    now = time.time()
    if now - _last_move_ts >= 2.0:
        _push({"type": "mouse_move", "time": _ts(), "x": x, "y": y})
        _last_move_ts = now

# ── Screenshot thread ────────────────────────────────────────────────────────
_ss_count = 0

def _screenshot_loop():
    global _ss_count
    while session["running"]:
        try:
            _ss_count += 1
            win  = _get_window()
            fname = f"ss_{_ss_count:04d}_{datetime.datetime.now().strftime('%H%M%S')}.jpg"
            fpath = Path(session["log_dir"]) / "screenshots" / fname
            fpath.parent.mkdir(exist_ok=True)
            img = ImageGrab.grab()
            img.save(fpath, "JPEG", quality=70, optimize=True)
            _push({
                "type": "screenshot",
                "time": _ts(),
                "file": fname,
                "window": win["title"],
            })
        except Exception as e:
            pass
        time.sleep(session["screenshot_interval"])

# ── Disk flush thread ────────────────────────────────────────────────────────
def _flush_loop(encryptor=None):
    """Flush buffer to disk (optionally encrypted) every 5 seconds"""
    while session["running"]:
        time.sleep(5)
        _flush_now(encryptor)

def _flush_now(encryptor=None):
    with _buffer_lock:
        if not _event_buffer: return
        batch = _event_buffer.copy()
        _event_buffer.clear()

    lines = "\n".join(json.dumps(e, ensure_ascii=False) for e in batch) + "\n"
    raw_path = Path(session["log_dir"]) / "events.jsonl"

    if encryptor:
        encryptor.append_encrypted(raw_path, lines)
    else:
        with open(raw_path, "a", encoding="utf-8") as f:
            f.write(lines)

# ── Public API ───────────────────────────────────────────────────────────────
_kb_listener = None
_ms_listener = None
_ss_thread   = None
_flush_thread = None

def start(log_dir: str, screenshot_interval: int = 30, encryptor=None):
    global _kb_listener, _ms_listener, _ss_thread, _flush_thread

    session["id"]       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    session["log_dir"]  = log_dir
    session["running"]  = True
    session["screenshot_interval"] = screenshot_interval

    Path(log_dir).mkdir(parents=True, exist_ok=True)

    _kb_listener = keyboard.Listener(on_press=on_key_press, on_release=on_key_release)
    _ms_listener = mouse.Listener(on_click=on_click, on_scroll=on_scroll, on_move=on_move)
    _ss_thread   = threading.Thread(target=_screenshot_loop, daemon=True)
    _flush_thread = threading.Thread(target=_flush_loop, args=(encryptor,), daemon=True)

    _kb_listener.start()
    _ms_listener.start()
    _ss_thread.start()
    _flush_thread.start()

def stop(encryptor=None):
    session["running"] = False
    if _kb_listener: _kb_listener.stop()
    if _ms_listener: _ms_listener.stop()
    _flush_now(encryptor)  # Final flush

def get_buffer_snapshot():
    """Return current buffer (for live dashboard)"""
    with _buffer_lock:
        return list(_event_buffer)
