"""
WorkGuard AI - Main Entry Point
Starts recorder + ML engine + API server + opens dashboard
"""

import os
import sys
import time
import json
import datetime
import getpass
import threading
import webbrowser
from pathlib import Path

# Fix: Ensure project root is in Python path
# camera_guard global
camera_guard = None
sys.path.insert(0, str(Path(__file__).resolve().parent))

# ── ASCII Banner ──────────────────────────────────────────────────────────────
BANNER = """
╔══════════════════════════════════════════════════════╗
║                                                      ║
║   ██╗    ██╗ ██████╗ ██████╗ ██╗  ██╗                ║
║   ██║    ██║██╔═══██╗██╔══██╗██║ ██╔╝                ║
║   ██║ █╗ ██║██║   ██║██████╔╝█████╔╝                 ║
║   ██║███╗██║██║   ██║██╔══██╗██╔═██╗                 ║
║   ╚███╔███╔╝╚██████╔╝██║  ██║██║  ██╗                ║
║    ╚══╝╚══╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝               ║
║                                                      ║
║   ██████╗ ██╗   ██╗ █████╗ ██████╗ ██████╗           ║
║  ██╔════╝ ██║   ██║██╔══██╗██╔══██╗██╔══██╗          ║
║  ██║  ███╗██║   ██║███████║██████╔╝██║  ██║          ║
║  ██║   ██║██║   ██║██╔══██║██╔══██╗██║  ██║          ║
║  ╚██████╔╝╚██████╔╝██║  ██║██║  ██║██████╔╝          ║
║   ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝           ║
║                                                      ║
║   AI-Powered Workspace Security Monitor v2.0         ║
╚══════════════════════════════════════════════════════╝
"""

def install_deps():
    """Auto-install all required packages"""
    packages = [
        "pynput", "Pillow", "pywin32", "psutil",
        "flask", "flask-cors", "cryptography",
        "scikit-learn", "numpy", "plyer"
    ]
    print("📦 Checking dependencies...")
    import subprocess
    for pkg in packages:
        try:
            __import__(pkg.replace('-','_').split('[')[0])
        except ImportError:
            print(f"   Installing {pkg}...", end=" ", flush=True)
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', pkg, '-q'],
                capture_output=True
            )
            print("✓" if result.returncode == 0 else "✗")
    print("✅ All dependencies ready\n")

def main():
    print(BANNER)
    
    # ── Install deps ────────────────────────────────────────────────────────
    install_deps()

    # ── Config ──────────────────────────────────────────────────────────────
    print("═" * 54)
    print("  CONFIGURATION")
    print("═" * 54)

    use_encryption = input("  Enable AES-256 encryption? (y/n) [y]: ").strip().lower() != 'n'
    password = None
    encryptor = None

    if use_encryption:
        password = getpass.getpass("  Set encryption password: ")
        if not password:
            print("  ⚠️  No password set — encryption disabled")
            use_encryption = False
        else:
            sys.path.insert(0, str(Path(__file__).parent))
            from core.encryptor import AESEncryptor, derive_key_info
            encryptor = AESEncryptor(password)
            info = derive_key_info(password)
            print(f"  🔑 Key fingerprint: {info['fingerprint']} ({info['algorithm']})")

    screenshot_interval = 30
    si = input(f"  Screenshot interval (seconds) [{screenshot_interval}]: ").strip()
    if si.isdigit():
        screenshot_interval = int(si)

    enable_api = input("  Launch live dashboard? (y/n) [y]: ").strip().lower() != 'n'
    api_port = 5000

    # ── Telegram setup
    enable_telegram = input("  Enable Telegram alerts? (y/n) [n]: ").strip().lower() == 'y'
    telegram_config = {"enabled": False}
    if enable_telegram:
        from core.telegram_alert import setup_telegram
        telegram_config = setup_telegram()

    # ── Idle Watcher setup
    enable_idle = input("  Enable idle detection? (y/n) [y]: ").strip().lower() != 'n'
    idle_minutes = 5
    if enable_idle:
        im = input("  Idle threshold minutes [5]: ").strip()
        if im.isdigit():
            idle_minutes = int(im)

    # ── Auto-start setup
    from core.autostart import is_autostart_enabled, enable_autostart
    if not is_autostart_enabled():
        do_autostart = input("  Auto-start on Windows boot? (y/n) [n]: ").strip().lower() == 'y'
        if do_autostart:
            res = enable_autostart()
            print(f"  Auto-start: {'Enabled' if res['success'] else 'Failed'}")
    else:
        print("  Auto-start: Already enabled")

    # ── Camera setup ─────────────────────────────────────────────────────────
    enable_camera = input("  Enable camera surveillance? (y/n) [y]: ").strip().lower() != 'n'

    print()

    # ── Setup paths ─────────────────────────────────────────────────────────
    session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir    = Path("activity_logs") / session_id
    log_dir.mkdir(parents=True, exist_ok=True)

    # Save session meta
    meta = {
        "session_id": session_id,
        "start_time": datetime.datetime.now().isoformat(),
        "computer_user": os.environ.get("USERNAME", "Unknown"),
        "hostname": os.environ.get("COMPUTERNAME", "Unknown"),
        "encrypted": use_encryption,
        "screenshot_interval": screenshot_interval,
    }
    with open(log_dir / "session_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    # ── Initialize Database ──────────────────────────────────────────────────
    from database.db import WorkGuardDB
    db = WorkGuardDB(db_path=str(log_dir / "workguard.db"))
    db.create_session(session_id, meta)

    # ── Start recorder ───────────────────────────────────────────────────────
    from core import recorder
    recorder.start(
        log_dir=str(log_dir),
        screenshot_interval=screenshot_interval,
        encryptor=encryptor
    )
    recorder.session["id"] = session_id
    recorder.session["running"] = True

    print("═" * 54)
    print("  SESSION STARTED")
    print("═" * 54)
    print(f"  Session ID : {session_id}")
    print(f"  Log folder : {log_dir.absolute()}")
    print(f"  Encryption : {'✅ AES-256-GCM' if use_encryption else '❌ Disabled'}")
    print(f"  Screenshots: every {screenshot_interval}s")

    # ── Start Camera Guard ────────────────────────────────────────────────────
    global camera_guard
    if enable_camera:
        try:
            from core.camera import CameraGuard
            from core.alerts import AlertManager
            _alert_mgr = AlertManager()

            def on_state_change(new_state):
                """Camera state change pe recording mode adjust karo"""
                from core.camera import STATE_STRANGER, STATE_NO_ONE, STATE_OWNER_PRESENT
                if new_state == STATE_STRANGER:
                    print("  🔴 STRANGER DETECTED — Full recording ON")
                elif new_state == STATE_NO_ONE:
                    print("  💤 Desk empty — Standby mode")
                elif new_state == STATE_OWNER_PRESENT:
                    print("  ✅ Owner back — Normal mode")

            camera_guard = CameraGuard(
                data_dir=str(Path("activity_logs")),
                alert_manager=_alert_mgr,
                on_state_change=on_state_change
            )

            # Register owner if no profile
            if not camera_guard.has_owner_profile():
                print()
                print("  ⚠️  Face profile nahi mili!")
                register_now = input("  Abhi register karo? (y/n) [y]: ").strip().lower() != 'n'
                if register_now:
                    result = camera_guard.register_owner(num_samples=8)
                    if not result["success"]:
                        print(f"  ❌ Registration failed: {result['error']}")
                        camera_guard = None

            if camera_guard:
                camera_guard.start()
                print(f"  Camera     : ✅ Active ({'Face ID' if camera_guard.has_owner_profile() else 'Presence only'})")
        except Exception as e:
            print(f"  Camera     : ❌ Failed ({e})")
            camera_guard = None
    else:
        print(f"  Camera     : ❌ Disabled")
    # ── Start Idle Watcher
    idle_watcher = None
    if enable_idle:
        try:
            from core.idle_watcher import setup_idle_watcher
            idle_watcher = setup_idle_watcher(
                idle_minutes=idle_minutes,
                away_minutes=idle_minutes * 3,
                camera_guard=camera_guard,
            )
            idle_watcher.start()
            print(f"  Idle Watch : ✅ Active (idle after {idle_minutes}min)")
        except Exception as e:
            print(f"  Idle Watch : ❌ Failed ({e})")

    tg_status = "✅ Active" if telegram_config.get("enabled") else "❌ Disabled"
    print(f"  Telegram   : {tg_status}")
    if telegram_config.get("enabled"):
        from core.telegram_alert import TelegramAlert
        _tg = TelegramAlert(telegram_config["token"], telegram_config["chat_id"])
        _tg.send_alert("SESSION_START", 0.0, details={"window": "WorkGuard AI", "process": "main.py"})

    # ── Start API + Dashboard ────────────────────────────────────────────────
    if enable_api:
        try:
            from api.server import run_api
            run_api(port=api_port)
            time.sleep(1.5)
            url = f"http://127.0.0.1:{api_port}"
            print(f"  Dashboard  : {url}")
            print()
            webbrowser.open(url)
        except Exception as e:
            print(f"  ⚠️  API failed to start: {e}")

    print()
    print("  ✅ WorkGuard AI is ACTIVE")
    print("  Press Ctrl+C to stop and generate report")
    print("═" * 54)
    print()

    # ── Main loop ────────────────────────────────────────────────────────────
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    # ── Shutdown ─────────────────────────────────────────────────────────────
    print("\n\n⏹️  Stopping WorkGuard AI...")
    recorder.stop(encryptor=encryptor)

    # ── Flush all events to DB ────────────────────────────────────────────────
    print("💾 Saving events to database...")
    try:
        event_file = log_dir / "events.jsonl"
        if event_file.exists():
            events = []
            with open(event_file) as f:
                for line in f:
                    try:
                        import json as _json
                        events.append(_json.loads(line))
                    except: pass
            inserted = db.bulk_insert_events(session_id, events)
            print(f"  ✅ {inserted} events saved to database")
        db.end_session(session_id)
        db.close()
    except Exception as e:
        print(f"  ⚠️ DB flush failed: {e}")
    if camera_guard:
        camera_guard.stop()

    # Update session meta with end time
    meta["end_time"] = datetime.datetime.now().isoformat()
    with open(log_dir / "session_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    # Generate HTML report
    print("📊 Generating report...")
    _generate_report(log_dir, encryptor, session_id, meta)

    print(f"\n🎉 Done! Report saved to:")
    print(f"   {(log_dir / 'report.html').absolute()}")
    print()


def _generate_report(log_dir: Path, encryptor, session_id: str, meta: dict):
    """Generate final HTML report"""
    events = []

    event_file = log_dir / "events.jsonl"
    enc_file   = log_dir / "events.enc"

    if enc_file.exists() and encryptor:
        try:
            raw = encryptor.decrypt_file(enc_file)
            for line in raw.splitlines():
                try: events.append(json.loads(line))
                except: pass
        except Exception as e:
            print(f"  ⚠️  Could not decrypt logs: {e}")
    elif event_file.exists():
        with open(event_file) as f:
            for line in f:
                try: events.append(json.loads(line))
                except: pass

    keystrokes  = [e for e in events if e.get("type") == "keystroke"]
    clicks      = [e for e in events if e.get("type") == "mouse_click"]
    scrolls     = [e for e in events if e.get("type") == "mouse_scroll"]
    screenshots = [e for e in events if e.get("type") == "screenshot"]

    # Window breakdown
    window_counts = {}
    window_keys   = {}
    for e in keystrokes:
        w = e.get("window", "Unknown")
        window_counts[w] = window_counts.get(w, 0) + 1
        window_keys.setdefault(w, []).append(e.get("key", ""))

    top_windows = sorted(window_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    def reconstruct(keys):
        t = ""
        for k in keys:
            if k == "[SPACE]": t += " "
            elif k == "[ENTER]": t += "\n"
            elif k == "[BACKSPACE]" and t: t = t[:-1]
            elif not k.startswith("["): t += k
        return t

    window_rows = ""
    for w, cnt in top_windows:
        pct = int(cnt / max(len(keystrokes), 1) * 100)
        typed = reconstruct(window_keys.get(w, []))[:400]
        typed_html = typed.replace('&','&amp;').replace('<','&lt;').replace('\n','<br>')
        window_rows += f"""
        <tr>
          <td class="tw">{w[:55]}</td>
          <td class="tc">{cnt}</td>
          <td><div class="bar" style="width:{max(pct,2)}%">{pct}%</div></td>
        </tr>
        <tr><td colspan="3" class="typed">{typed_html or '<i style="color:#444">No text reconstructed</i>'}</td></tr>"""

    ss_gallery = ""
    for ss in sorted((log_dir / "screenshots").glob("*.jpg")) if (log_dir / "screenshots").exists() else []:
        rel = ss.relative_to(log_dir)
        ss_gallery += f'<div class="ss"><img src="{rel}" loading="lazy" onclick="openModal(this.src)"><p>{ss.name}</p></div>'

    timeline_rows = ""
    for e in events[-200:]:
        icon = {"keystroke":"⌨️","mouse_click":"🖱️","screenshot":"📸","mouse_scroll":"📜"}.get(e.get("type",""),"•")
        detail = (e.get("key") or e.get("file") or e.get("direction") or e.get("button") or "")
        window_rows_tl = (e.get("window") or "")[:40]
        t = (e.get("time") or "").split("T")[-1][:8]
        timeline_rows += f"<tr><td class='tt'>{t}</td><td>{icon} {e.get('type','')}</td><td class='td2'>{str(detail)[:50]}</td><td class='tw2'>{window_rows_tl}</td></tr>"

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>WorkGuard AI — Report {session_id}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#080b14;color:#e0e0e0}}
.hdr{{background:linear-gradient(90deg,#0d1117,#111827);padding:24px 36px;border-bottom:1px solid #1f2937}}
.hdr h1{{font-size:24px;color:#3b82f6}}
.hdr p{{color:#6b7280;margin-top:4px;font-size:14px}}
.container{{max-width:1400px;margin:0 auto;padding:24px 20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:20px}}
.stat{{background:#111827;border:1px solid #1f2937;border-radius:10px;padding:18px;text-align:center}}
.stat .n{{font-size:40px;font-weight:800;color:#3b82f6}}
.stat .l{{font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;margin-top:4px}}
.section{{background:#111827;border:1px solid #1f2937;border-radius:10px;padding:22px;margin-bottom:18px}}
.section h2{{font-size:15px;color:#3b82f6;margin-bottom:14px;border-bottom:1px solid #1f2937;padding-bottom:10px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#0d1117;color:#6b7280;text-align:left;padding:9px 12px;font-size:11px;text-transform:uppercase;letter-spacing:.5px}}
td{{padding:7px 12px;border-bottom:1px solid #1a1f2e;vertical-align:top}}
tr:hover{{background:#0d1117}}
.tw{{color:#93c5fd;max-width:280px;word-break:break-all}}
.tc{{color:#ef4444;font-weight:700;width:70px}}
.bar{{background:linear-gradient(90deg,#3b82f6,#1d4ed8);height:20px;border-radius:3px;display:flex;align-items:center;padding:0 6px;font-size:11px;color:white;min-width:24px}}
.typed{{background:#0a0d16;font-family:monospace;font-size:12px;color:#10b981;padding:6px 12px;max-height:70px;overflow-y:auto;white-space:pre-wrap;word-break:break-all}}
.tt{{color:#6b7280;font-size:11px;font-family:monospace;white-space:nowrap}}
.td2{{font-family:monospace;font-size:12px;color:#94a3b8}}
.tw2{{color:#6b7280;font-size:11px}}
.gallery{{display:flex;flex-wrap:wrap;gap:10px}}
.ss img{{width:180px;height:110px;object-fit:cover;border:2px solid #1f2937;border-radius:6px;cursor:pointer}}
.ss img:hover{{border-color:#3b82f6}}
.ss p{{font-size:10px;color:#4b5563;margin-top:3px;text-align:center}}
.modal{{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.92);z-index:999;align-items:center;justify-content:center}}
.modal.on{{display:flex}}
.modal img{{max-width:95vw;max-height:90vh;border-radius:8px}}
.close{{position:fixed;top:16px;right:24px;color:white;font-size:28px;cursor:pointer;z-index:1000}}
.enc-badge{{display:inline-block;padding:3px 10px;background:#065f46;color:#34d399;border-radius:5px;font-size:11px;margin-left:10px}}
</style></head><body>
<div class="hdr">
  <h1>🛡️ WorkGuard AI — Session Report
    {'<span class="enc-badge">🔑 AES-256-GCM Encrypted</span>' if meta.get('encrypted') else ''}
  </h1>
  <p>Session: {session_id} &nbsp;|&nbsp; User: {meta.get('computer_user','?')} &nbsp;|&nbsp;
     Machine: {meta.get('hostname','?')} &nbsp;|&nbsp;
     {meta.get('start_time','?')[:19]} → {meta.get('end_time','?')[:19]}</p>
</div>
<div class="container">
  <div class="grid">
    <div class="stat"><div class="n">{len(keystrokes)}</div><div class="l">⌨️ Keystrokes</div></div>
    <div class="stat"><div class="n">{len(clicks)}</div><div class="l">🖱️ Mouse Clicks</div></div>
    <div class="stat"><div class="n">{len(scrolls)}</div><div class="l">📜 Scrolls</div></div>
    <div class="stat"><div class="n">{len(screenshots)}</div><div class="l">📸 Screenshots</div></div>
    <div class="stat"><div class="n">{len(top_windows)}</div><div class="l">🪟 Apps Used</div></div>
    <div class="stat"><div class="n">{len(events)}</div><div class="l">📊 Total Events</div></div>
  </div>

  <div class="section">
    <h2>🪟 App Activity & Typed Text</h2>
    <table><thead><tr><th>Window / App</th><th>Keys</th><th>Usage</th></tr></thead>
    <tbody>{window_rows}</tbody></table>
  </div>

  <div class="section">
    <h2>⏱️ Activity Timeline (Last 200 Events)</h2>
    <table><thead><tr><th>Time</th><th>Type</th><th>Detail</th><th>Window</th></tr></thead>
    <tbody>{timeline_rows}</tbody></table>
  </div>

  <div class="section">
    <h2>📸 Screenshots ({len(screenshots)} captured)</h2>
    <div class="gallery">{ss_gallery or '<p style="color:#4b5563">No screenshots in this session.</p>'}</div>
  </div>
</div>

<div class="modal" id="modal" onclick="closeModal()">
  <span class="close">✕</span>
  <img id="mimg" src="">
</div>
<script>
function openModal(src){{document.getElementById('mimg').src=src;document.getElementById('modal').classList.add('on')}}
function closeModal(){{document.getElementById('modal').classList.remove('on')}}
document.addEventListener('keydown',e=>{{if(e.key==='Escape')closeModal()}})
</script>
</body></html>"""

    with open(log_dir / "report.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✅ Report generated")


if __name__ == "__main__":
    main()
