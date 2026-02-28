"""
path_helper.py
Finds the actual Scripts directory where cdp-dev was installed,
handling the Windows Microsoft Store Python split-brain case.
"""
import os
import sys
import site
import platform
import sysconfig
from pathlib import Path


def find_scripts_dir() -> Path | None:
    """
    Find the Scripts directory that actually contains cdp-dev.
    Checks all plausible locations in order.
    """
    exe_name = "cdp-dev.exe" if platform.system() == "Windows" else "cdp-dev"
    candidates = _all_candidate_dirs()

    for candidate in candidates:
        if (candidate / exe_name).exists():
            return candidate

    # Fallback — return sysconfig default even if exe not found there
    return Path(sysconfig.get_path("scripts"))


def _all_candidate_dirs() -> list:
    candidates = []

    # Standard sysconfig path
    candidates.append(Path(sysconfig.get_path("scripts")))

    # User base Scripts (pip install --user target)
    if hasattr(site, "getuserbase"):
        base = Path(site.getuserbase())
        candidates.append(base / ("Scripts" if platform.system() == "Windows" else "bin"))

    # Microsoft Store Python — scan the Packages directory
    if platform.system() == "Windows":
        packages = Path.home() / "AppData" / "Local" / "Packages"
        if packages.exists():
            for pkg in sorted(packages.glob("PythonSoftwareFoundation.Python.*"), reverse=True):
                local_cache = pkg / "LocalCache" / "local-packages"
                if local_cache.exists():
                    for py_ver in sorted(local_cache.glob("Python*"), reverse=True):
                        candidates.append(py_ver / "Scripts")

    return candidates


def ensure_on_path():
    """Add the correct Scripts dir to PATH for the current process."""
    scripts_dir = find_scripts_dir()
    if scripts_dir is None:
        return
    scripts_str = str(scripts_dir)
    current = os.environ.get("PATH", "")
    if scripts_str not in current:
        sep = ";" if platform.system() == "Windows" else ":"
        os.environ["PATH"] = current + sep + scripts_str


def is_cdpdev_on_path() -> bool:
    import shutil
    return shutil.which("cdp-dev") is not None


def get_scripts_dir() -> Path:
    return find_scripts_dir() or Path(sysconfig.get_path("scripts"))


def fix_path_windows():
    if platform.system() != "Windows":
        return

    scripts_dir = find_scripts_dir()
    if scripts_dir is None:
        return

    ensure_on_path()
    scripts_str = str(scripts_dir)

    try:
        import winreg, ctypes
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment",
                             0, winreg.KEY_READ | winreg.KEY_WRITE)
        try:
            current, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current = ""

        if scripts_str.lower() not in current.lower():
            new_path = f"{current};{scripts_str}" if current else scripts_str
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
            ctypes.windll.user32.SendMessageTimeoutW(
                0xFFFF, 0x001A, 0, "Environment", 2, 5000, None
            )
        winreg.CloseKey(key)
    except Exception:
        pass
