"""
WorkGuard AI - Auto Cleanup Manager
Automatically deletes old logs, screenshots to save storage.

Features:
- Old sessions delete karo (configurable days)
- Screenshots compress/delete karo
- Storage usage report dikhao
- Scheduled cleanup (runs daily)
"""

import os
import sys
import json
import time
import shutil
import threading
import datetime
from pathlib import Path

ROOT       = Path(__file__).resolve().parent
LOGS_DIR   = ROOT / "activity_logs"
CONFIG     = ROOT / "config.json"

def load_config() -> dict:
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except:
        return {"keep_logs_days": 7, "max_storage_mb": 500}

def get_folder_size(path: Path) -> int:
    """Return folder size in bytes"""
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except:
        pass
    return total

def format_size(bytes: int) -> str:
    """Human readable size"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024
    return f"{bytes:.1f} GB"

def get_storage_report() -> dict:
    """Get current storage usage"""
    if not LOGS_DIR.exists():
        return {"total": 0, "sessions": [], "screenshots": 0}

    sessions = []
    total_screenshots = 0
    total_size = 0

    for session_dir in sorted(LOGS_DIR.iterdir(), reverse=True):
        if not session_dir.is_dir():
            continue

        # Session size
        size = get_folder_size(session_dir)
        total_size += size

        # Screenshots count
        ss_dir = session_dir / "screenshots"
        ss_count = len(list(ss_dir.glob("*.jpg"))) if ss_dir.exists() else 0
        total_screenshots += ss_count

        # Session date
        try:
            date = datetime.datetime.strptime(session_dir.name, "%Y%m%d_%H%M%S")
            age_days = (datetime.datetime.now() - date).days
        except:
            age_days = 0

        sessions.append({
            "id": session_dir.name,
            "size": size,
            "size_str": format_size(size),
            "screenshots": ss_count,
            "age_days": age_days,
            "path": str(session_dir),
        })

    return {
        "total": total_size,
        "total_str": format_size(total_size),
        "sessions": sessions,
        "total_screenshots": total_screenshots,
        "session_count": len(sessions),
    }

def delete_old_sessions(keep_days: int = 7, dry_run: bool = False) -> dict:
    """Delete sessions older than keep_days"""
    if not LOGS_DIR.exists():
        return {"deleted": 0, "freed": 0}

    deleted = 0
    freed   = 0
    cutoff  = datetime.datetime.now() - datetime.timedelta(days=keep_days)

    for session_dir in LOGS_DIR.iterdir():
        if not session_dir.is_dir():
            continue
        try:
            date = datetime.datetime.strptime(session_dir.name, "%Y%m%d_%H%M%S")
        except:
            continue

        if date < cutoff:
            size = get_folder_size(session_dir)
            if not dry_run:
                shutil.rmtree(session_dir)
                print(f"  🗑️  Deleted: {session_dir.name} ({format_size(size)})")
            else:
                print(f"  [DRY RUN] Would delete: {session_dir.name} ({format_size(size)})")
            deleted += 1
            freed   += size

    return {"deleted": deleted, "freed": freed, "freed_str": format_size(freed)}

def delete_old_screenshots(keep_days: int = 3, dry_run: bool = False) -> dict:
    """Delete screenshots older than keep_days but keep events/logs"""
    if not LOGS_DIR.exists():
        return {"deleted": 0, "freed": 0}

    deleted = 0
    freed   = 0
    cutoff  = datetime.datetime.now() - datetime.timedelta(days=keep_days)

    for session_dir in LOGS_DIR.iterdir():
        if not session_dir.is_dir():
            continue

        try:
            date = datetime.datetime.strptime(session_dir.name, "%Y%m%d_%H%M%S")
        except:
            continue

        if date < cutoff:
            ss_dir = session_dir / "screenshots"
            if ss_dir.exists():
                for img in ss_dir.glob("*.jpg"):
                    size = img.stat().st_size
                    if not dry_run:
                        img.unlink()
                    deleted += 1
                    freed   += size

    if not dry_run and deleted > 0:
        print(f"  🗑️  Deleted {deleted} screenshots ({format_size(freed)} freed)")

    return {"deleted": deleted, "freed": freed, "freed_str": format_size(freed)}

def enforce_storage_limit(max_mb: int = 500, dry_run: bool = False) -> dict:
    """Delete oldest sessions if storage exceeds max_mb"""
    max_bytes = max_mb * 1024 * 1024
    report    = get_storage_report()

    if report["total"] <= max_bytes:
        return {"deleted": 0, "freed": 0, "message": "Storage OK"}

    freed   = 0
    deleted = 0

    # Sort sessions by age (oldest first)
    sessions = sorted(report["sessions"], key=lambda x: x["age_days"], reverse=True)

    for sess in sessions:
        if report["total"] - freed <= max_bytes:
            break
        if not dry_run:
            shutil.rmtree(sess["path"], ignore_errors=True)
            print(f"  🗑️  Storage limit: deleted {sess['id']} ({sess['size_str']})")
        freed   += sess["size"]
        deleted += 1

    return {"deleted": deleted, "freed": freed, "freed_str": format_size(freed)}

def run_cleanup(verbose: bool = True) -> dict:
    """Main cleanup function — run this daily"""
    cfg = load_config()
    keep_days     = cfg.get("keep_logs_days", 7)
    keep_ss_days  = cfg.get("keep_screenshots_days", 3)
    max_storage   = cfg.get("max_storage_mb", 500)

    if verbose:
        print("\n  🧹 WorkGuard AI — Auto Cleanup")
        print("  " + "─"*40)

    # Before
    before = get_folder_size(LOGS_DIR) if LOGS_DIR.exists() else 0

    # Delete old sessions
    r1 = delete_old_sessions(keep_days=keep_days)

    # Delete old screenshots (but keep event logs)
    r2 = delete_old_screenshots(keep_days=keep_ss_days)

    # Enforce storage limit
    r3 = enforce_storage_limit(max_mb=max_storage)

    # After
    after = get_folder_size(LOGS_DIR) if LOGS_DIR.exists() else 0
    total_freed = before - after

    if verbose:
        print(f"\n  ✅ Cleanup complete!")
        print(f"  Sessions deleted : {r1['deleted']}")
        print(f"  Screenshots del  : {r2['deleted']}")
        print(f"  Total freed      : {format_size(total_freed)}")
        print(f"  Current usage    : {format_size(after)}")
        print()

    # Log cleanup
    try:
        log_file = ROOT / "activity_logs" / "cleanup.log"
        log_file.parent.mkdir(exist_ok=True)
        with open(log_file, 'a') as f:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] Freed: {format_size(total_freed)} | "
                   f"Sessions: {r1['deleted']} | Screenshots: {r2['deleted']}\n")
    except:
        pass

    return {
        "sessions_deleted": r1["deleted"],
        "screenshots_deleted": r2["deleted"],
        "total_freed": total_freed,
        "total_freed_str": format_size(total_freed),
        "current_usage": format_size(after),
    }

def schedule_daily_cleanup():
    """Run cleanup every 24 hours in background thread"""
    def _loop():
        while True:
            # Wait until 3 AM
            now    = datetime.datetime.now()
            target = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if target <= now:
                target += datetime.timedelta(days=1)
            wait_seconds = (target - now).total_seconds()
            time.sleep(wait_seconds)
            run_cleanup(verbose=False)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return t

def print_storage_report():
    """Print detailed storage report"""
    report = get_storage_report()
    cfg    = load_config()
    max_mb = cfg.get("max_storage_mb", 500)
    used   = report["total"] / (1024*1024)
    pct    = (used / max_mb * 100) if max_mb > 0 else 0

    print("\n  📊 WorkGuard AI — Storage Report")
    print("  " + "─"*40)
    print(f"  Total sessions    : {report['session_count']}")
    print(f"  Total screenshots : {report['total_screenshots']}")
    print(f"  Storage used      : {report['total_str']}")
    print(f"  Storage limit     : {max_mb} MB")
    print(f"  Usage             : {pct:.1f}%")

    # Bar chart
    bar_len = 30
    filled  = int(bar_len * pct / 100)
    bar     = "█" * filled + "░" * (bar_len - filled)
    color   = "🟢" if pct < 60 else "🟡" if pct < 85 else "🔴"
    print(f"  [{bar}] {color}")

    if report["sessions"]:
        print(f"\n  Recent sessions:")
        for s in report["sessions"][:5]:
            print(f"  • {s['id']} — {s['size_str']} — "
                  f"{s['screenshots']} screenshots — {s['age_days']}d old")
    print()

# ── CLI Interface ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]

    if "--report" in args or "-r" in args:
        print_storage_report()

    elif "--dry-run" in args:
        print("\n  [DRY RUN] — No files will be deleted\n")
        cfg = load_config()
        delete_old_sessions(keep_days=cfg.get("keep_logs_days", 7), dry_run=True)
        delete_old_screenshots(keep_days=cfg.get("keep_screenshots_days", 3), dry_run=True)

    elif "--now" in args or len(args) == 0:
        run_cleanup(verbose=True)

    elif "--schedule" in args:
        print("  ⏰ Scheduled cleanup — runs daily at 3 AM")
        schedule_daily_cleanup()
        # Keep alive
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
    else:
        print("""
  WorkGuard AI — Cleanup Manager

  Usage:
    python cleanup.py              # Run cleanup now
    python cleanup.py --report     # Show storage report
    python cleanup.py --dry-run    # Preview what will be deleted
    python cleanup.py --schedule   # Run daily at 3 AM

  Config (config.json):
    keep_logs_days       : Days to keep session logs (default: 7)
    keep_screenshots_days: Days to keep screenshots (default: 3)
    max_storage_mb       : Maximum storage limit in MB (default: 500)
        """)
