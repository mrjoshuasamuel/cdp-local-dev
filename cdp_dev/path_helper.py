"""
path_helper.py
Automatically detects and fixes the PATH for this specific machine and user.
Never hardcodes any paths — uses sysconfig to find where pip installed scripts.
"""
import os
import sys
import platform
import sysconfig
from pathlib import Path


def get_scripts_dir() -> Path:
    """
    Returns the directory where pip installs console_scripts entry points.
    This is always correct for the current Python installation and user,
    regardless of OS, username, or Python version.

    Examples:
      Windows: C:\\Users\\<username>\\AppData\\Local\\...\\Scripts
      macOS:   /Users/<username>/Library/Python/3.11/bin
      Linux:   /home/<username>/.local/bin
    """
    return Path(sysconfig.get_path("scripts"))


def is_cdpdev_on_path() -> bool:
    import shutil
    return shutil.which("cdp-dev") is not None


def ensure_on_path():
    """
    Silently adds the Scripts dir to PATH for the current process.
    Called at startup of every CLI command so cdp-dev always works
    even if the user hasn't run bootstrap.py yet.
    """
    scripts_dir = str(get_scripts_dir())
    current_path = os.environ.get("PATH", "")

    if scripts_dir not in current_path:
        if platform.system() == "Windows":
            os.environ["PATH"] = current_path + ";" + scripts_dir
        else:
            os.environ["PATH"] = scripts_dir + ":" + current_path


def fix_path_windows():
    """
    Persist the Scripts directory to the Windows user PATH registry key
    so it survives terminal restarts. Also broadcasts the change so new
    terminals pick it up immediately without a reboot.
    Uses sysconfig — no hardcoded paths.
    """
    if platform.system() != "Windows":
        return

    scripts_dir = str(get_scripts_dir())

    # Fix current process immediately
    ensure_on_path()

    try:
        import winreg
        import ctypes

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            "Environment",
            0,
            winreg.KEY_READ | winreg.KEY_WRITE
        )
        try:
            current, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current = ""

        if scripts_dir.lower() not in current.lower():
            new_path = f"{current};{scripts_dir}" if current else scripts_dir
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)

            # Broadcast so open terminals and new terminals pick up the change
            HWND_BROADCAST   = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", 2, 5000, None
            )

        winreg.CloseKey(key)

    except Exception:
        pass  # Silently skip — ensure_on_path() already fixed the current session
