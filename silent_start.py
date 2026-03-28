"""
WorkGuard AI - Silent Auto-Start Launcher
Runs when Windows boots - no questions, no console window.
Reads config.json for all settings.

Usage:
  python silent_start.py          # Run silently
  python silent_start.py --setup  # First time setup wizard
"""

import os
import sys
import json
import time
import datetime
import threading
import webbrowser
from pathlib import Path

# ── Fix import paths ──────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

CONFIG_FILE = ROOT / "config.json"
LOG_FILE    = ROOT / "activity_logs" / "autostart.log"

def log(msg):
    """Write to log file silently"""
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, 'a') as f:
            f.write(f"[{timestamp}] {msg}\n")
    except:
        pass

def load_config() -> dict:
    """Load config.json - create default if missing"""
    default = {
        "encryption": False,
        "screenshot_interval": 30,
        "enable_dashboard": True,
        "dashboard_port": 5000,
        "enable_camera": True,
        "idle_minutes": 5,
        "away_minutes": 15,
        "enable_telegram": False,
        "telegram_token": "",
        "telegram_chat_id": "",
        "auto_start_browser": False,
        "silent_mode": True
    }
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
            default.update(cfg)
        except:
            log("Config read failed — using defaults")
    else:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default, f, indent=2)
        log("Created default config.json")
    return default

def setup_wizard():
    """Interactive first-time setup"""
    print("\n" + "="*54)
    print("  WorkGuard AI — First Time Setup")
    print("="*54)

    cfg = load_config()

    print("\n  This wizard will configure WorkGuard AI.")
    print("  Settings will be saved to config.json")
    print("  After setup, system will auto-start on every boot.\n")

    # Camera
    cam = input("  Enable camera surveillance? (y/n) [y]: ").strip().lower()
    cfg["enable_camera"] = cam != 'n'

    # Idle time
    idle = input("  Idle detection threshold (minutes) [5]: ").strip()
    cfg["idle_minutes"] = int(idle) if idle.isdigit() else 5

    # Dashboard
    dash = input("  Show dashboard? (y/n) [y]: ").strip().lower()
    cfg["enable_dashboard"] = dash != 'n'

    # Browser
    if cfg["enable_dashboard"]:
        browser = input("  Auto-open browser on start? (y/n) [n]: ").strip().lower()
        cfg["auto_start_browser"] = browser == 'y'

    # Telegram
    tg = input("  Enable Telegram alerts? (y/n) [n]: ").strip().lower()
    cfg["enable_telegram"] = tg == 'y'
    if cfg["enable_telegram"]:
        cfg["telegram_token"]   = input("  Telegram Bot Token: ").strip()
        cfg["telegram_chat_id"] = input("  Telegram Chat ID: ").strip()

    # Encryption
    enc = input("  Enable AES-256 log encryption? (y/n) [n]: ").strip().lower()
    cfg["encryption"] = enc == 'y'
    if cfg["encryption"]:
        import getpass
        pwd = getpass.getpass("  Encryption password: ")
        cfg["encryption_password"] = pwd

    # Screenshot interval
    si = input("  Screenshot interval seconds [30]: ").strip()
    cfg["screenshot_interval"] = int(si) if si.isdigit() else 30

    # Save config
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)
    print("\n  ✅ Config saved to config.json")

    # Enable Windows auto-start
    enable = input("\n  Enable auto-start on Windows boot? (y/n) [y]: ").strip().lower()
    if enable != 'n':
        from core.autostart import enable_autostart
        # Point to silent_start.py instead of main.py
        result = enable_autostart_silent()
        if result["success"]:
            print("  ✅ Auto-start enabled! WorkGuard AI will start silently on boot.")
        else:
            print(f"  ❌ Auto-start failed: {result.get('error')}")

    print("\n  Setup complete! Run: python silent_start.py")
    print("="*54 + "\n")

def enable_autostart_silent() -> dict:
    """Register silent_start.py in Windows startup"""
    try:
        import winreg
        REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
        APP_NAME = "WorkGuardAI"

        python_exe = sys.executable
        pythonw    = python_exe.replace("python.exe", "pythonw.exe")
        script     = str(ROOT / "silent_start.py")

        if Path(pythonw).exists():
            cmd = f'"{pythonw}" "{script}"'
        else:
            cmd = f'"{python_exe}" "{script}"'

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            REG_PATH, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        log(f"Auto-start registered: {cmd}")
        return {"success": True, "command": cmd}
    except Exception as e:
        log(f"Auto-start registration failed: {e}")
        return {"success": False, "error": str(e)}

def main_silent():
    """Run WorkGuard AI silently using config.json"""
    log("WorkGuard AI starting (silent mode)...")
    cfg = load_config()

    # ── Session setup ─────────────────────────────────────────────────────────
    session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir    = ROOT / "activity_logs" / session_id
    log_dir.mkdir(parents=True, exist_ok=True)

    # Save meta
    import json as _json
    meta = {
        "session_id": session_id,
        "start_time": datetime.datetime.now().isoformat(),
        "computer_user": os.environ.get("USERNAME", "Unknown"),
        "hostname": os.environ.get("COMPUTERNAME", "Unknown"),
        "encrypted": cfg.get("encryption", False),
        "screenshot_interval": cfg.get("screenshot_interval", 30),
        "silent_mode": True,
    }
    with open(log_dir / "session_meta.json", 'w') as f:
        _json.dump(meta, f, indent=2)

    log(f"Session: {session_id}")

    # ── Encryption setup ──────────────────────────────────────────────────────
    encryptor = None
    if cfg.get("encryption") and cfg.get("encryption_password"):
        try:
            from core.encryptor import AESEncryptor
            encryptor = AESEncryptor(cfg["encryption_password"])
            log("Encryption: AES-256-GCM active")
        except Exception as e:
            log(f"Encryption failed: {e}")

    # ── Start recorder ────────────────────────────────────────────────────────
    try:
        from core import recorder
        recorder.start(
            log_dir=str(log_dir),
            screenshot_interval=cfg.get("screenshot_interval", 30),
            encryptor=encryptor
        )
        recorder.session["id"]      = session_id
        recorder.session["running"] = True
        log("Recorder: started")
    except Exception as e:
        log(f"Recorder failed: {e}")
        return

    # ── Telegram setup ────────────────────────────────────────────────────────
    telegram = None
    if cfg.get("enable_telegram") and cfg.get("telegram_token"):
        try:
            from core.telegram_alert import TelegramAlert
            telegram = TelegramAlert(
                cfg["telegram_token"],
                cfg["telegram_chat_id"]
            )
            telegram.send_message(
                f"🟢 <b>WorkGuard AI Started</b>\n"
                f"Session: {session_id}\n"
                f"Time: {datetime.datetime.now().strftime('%d %b %Y, %I:%M %p')}"
            )
            log("Telegram: connected")
        except Exception as e:
            log(f"Telegram failed: {e}")

    # ── Camera + Idle watcher ─────────────────────────────────────────────────
    camera_guard = None
    idle_watcher  = None

    if cfg.get("enable_camera"):
        try:
            from core.camera import CameraGuard

            def on_state_change(state):
                log(f"Camera state: {state}")
                if state == "STRANGER" and telegram:
                    # Capture intruder photo
                    photo = camera_guard.capture_intruder_photo(str(log_dir))
                    photo_path = str(log_dir / photo) if photo else None
                    telegram.send_alert(
                        "STRANGER_DETECTED",
                        score=0.95,
                        screenshot_path=photo_path,
                        details={"window": "Camera", "process": "camera_guard"}
                    )

            camera_guard = CameraGuard(
                data_dir=str(ROOT / "activity_logs"),
                alert_manager=None,
                on_state_change=on_state_change
            )
            camera_guard.start()
            log("Camera: started")
        except Exception as e:
            log(f"Camera failed: {e}")

    # ── Idle watcher ──────────────────────────────────────────────────────────
    try:
        from core.idle_watcher import setup_idle_watcher
        idle_watcher = setup_idle_watcher(
            idle_minutes=cfg.get("idle_minutes", 5),
            away_minutes=cfg.get("away_minutes", 15),
            camera_guard=camera_guard,
            telegram=telegram
        )
        idle_watcher.start()
        log("Idle watcher: started")
    except Exception as e:
        log(f"Idle watcher failed: {e}")

    # ── Flask API ─────────────────────────────────────────────────────────────
    if cfg.get("enable_dashboard"):
        try:
            from api.server import run_api
            run_api(port=cfg.get("dashboard_port", 5000))
            time.sleep(1.5)
            log(f"Dashboard: http://127.0.0.1:{cfg.get('dashboard_port', 5000)}")

            if cfg.get("auto_start_browser"):
                webbrowser.open(f"http://127.0.0.1:{cfg.get('dashboard_port', 5000)}")
        except Exception as e:
            log(f"Dashboard failed: {e}")

    log("All systems active — monitoring started")

    # ── Main loop ─────────────────────────────────────────────────────────────
    try:
        while True:
            time.sleep(5)
    except (KeyboardInterrupt, SystemExit):
        pass

    # ── Shutdown ──────────────────────────────────────────────────────────────
    log("Shutting down...")
    try:
        recorder.stop(encryptor=encryptor)
        if camera_guard: camera_guard.stop()
        if idle_watcher: idle_watcher.stop()
        log("Clean shutdown complete")
    except Exception as e:
        log(f"Shutdown error: {e}")


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--setup" in sys.argv:
        setup_wizard()
    else:
        # Small delay on boot — wait for network/camera to init
        if "--boot" in sys.argv:
            time.sleep(10)
        main_silent()
