"""
WorkGuard AI - Windows Auto-Start Manager
Adds/removes WorkGuard AI from Windows startup using Registry.

Method: HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
This starts the app silently when Windows boots — no admin rights needed.
"""

import os
import sys
import subprocess
from pathlib import Path

try:
    import winreg
    WINREG_OK = True
except ImportError:
    WINREG_OK = False

# Registry key path
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "WorkGuardAI"


def enable_autostart(project_dir: str = None) -> dict:
    """
    Add WorkGuard AI to Windows startup.
    Runs silently using pythonw (no console window).
    """
    if not WINREG_OK:
        return {"success": False, "error": "Windows only"}

    if project_dir is None:
        project_dir = str(Path(__file__).parent.parent)

    main_script = Path(project_dir) / "main.py"
    if not main_script.exists():
        return {"success": False, "error": f"main.py not found in {project_dir}"}

    # Use pythonw for silent startup (no console window)
    python_exe = sys.executable
    pythonw    = python_exe.replace("python.exe", "pythonw.exe")

    # If pythonw exists use it, else use python with --silent flag
    if Path(pythonw).exists():
        cmd = f'"{pythonw}" "{main_script}" --silent'
    else:
        cmd = f'"{python_exe}" "{main_script}" --silent'

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REG_PATH,
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)

        print(f"  ✅ Auto-start enabled!")
        print(f"  Command: {cmd}")
        return {"success": True, "command": cmd}

    except Exception as e:
        return {"success": False, "error": str(e)}


def disable_autostart() -> dict:
    """Remove WorkGuard AI from Windows startup"""
    if not WINREG_OK:
        return {"success": False, "error": "Windows only"}

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REG_PATH,
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
        print("  ✅ Auto-start disabled!")
        return {"success": True}
    except FileNotFoundError:
        return {"success": False, "error": "Auto-start was not enabled"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def is_autostart_enabled() -> bool:
    """Check if auto-start is currently enabled"""
    if not WINREG_OK:
        return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REG_PATH,
            0,
            winreg.KEY_READ
        )
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def get_autostart_command() -> str:
    """Get current auto-start command"""
    if not WINREG_OK:
        return None
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REG_PATH,
            0,
            winreg.KEY_READ
        )
        value, _ = winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return value
    except Exception:
        return None


if __name__ == "__main__":
    print("\n  WorkGuard AI — Auto-Start Manager")
    print("  ──────────────────────────────────")

    if is_autostart_enabled():
        print(f"  Status: ✅ ENABLED")
        print(f"  Command: {get_autostart_command()}")
        print()
        choice = input("  Disable auto-start? (y/n): ").strip().lower()
        if choice == 'y':
            result = disable_autostart()
            print(f"  {'✅ Done!' if result['success'] else '❌ ' + result['error']}")
    else:
        print("  Status: ❌ DISABLED")
        print()
        choice = input("  Enable auto-start on Windows boot? (y/n): ").strip().lower()
        if choice == 'y':
            result = enable_autostart()
            if result["success"]:
                print("  WorkGuard AI will now start silently on every Windows boot!")
            else:
                print(f"  ❌ Failed: {result['error']}")
