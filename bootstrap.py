"""
bootstrap.py
Permanent PATH fix for cdp-dev on Windows.

Strategy: instead of fighting Windows PATH refresh timing,
drop a cdp-dev.bat wrapper into C:\Windows\System32 which is
ALWAYS on PATH in every terminal, immediately, forever.

Usage:
    python bootstrap.py
"""
import os
import sys
import site
import platform
import sysconfig
import ctypes
from pathlib import Path


# ── Find cdp-dev.exe wherever pip installed it ────────────────────────────────

def find_cdpdev_exe() -> Path | None:
    exe_name = "cdp-dev.exe" if platform.system() == "Windows" else "cdp-dev"
    for candidate in _candidate_dirs():
        exe = candidate / exe_name
        if exe.exists():
            return exe
    return None


def _candidate_dirs() -> list:
    dirs = []

    # 1. sysconfig default
    dirs.append(Path(sysconfig.get_path("scripts")))

    # 2. user base
    if hasattr(site, "getuserbase"):
        base = Path(site.getuserbase())
        dirs.append(base / ("Scripts" if platform.system() == "Windows" else "bin"))

    # 3. Microsoft Store Python — scan all versions
    if platform.system() == "Windows":
        packages = Path.home() / "AppData" / "Local" / "Packages"
        if packages.exists():
            for pkg in sorted(packages.glob("PythonSoftwareFoundation.Python.*"), reverse=True):
                local = pkg / "LocalCache" / "local-packages"
                if local.exists():
                    for py_ver in sorted(local.glob("Python*"), reverse=True):
                        dirs.append(py_ver / "Scripts")

    return dirs


# ── Windows: write cdp-dev.bat into System32 ─────────────────────────────────

def _is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _relaunch_as_admin():
    """Relaunch this script with UAC elevation."""
    print()
    print("  Administrator access needed to write to C:\\Windows\\System32.")
    print("  Windows will show a UAC prompt — click Yes to continue.")
    print()
    params = " ".join(f'"{a}"' for a in sys.argv)
    ret = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
    )
    if ret <= 32:
        print("  ✗  Could not get admin rights automatically.")
        print("  Right-click your terminal and choose 'Run as administrator',")
        print("  then run:  python bootstrap.py")
        sys.exit(1)
    sys.exit(0)


def install_bat_wrapper(cdp_exe: Path):
    """
    Write a cdp-dev.bat into C:\Windows\System32 that calls the real exe.
    This makes cdp-dev available in every terminal permanently with zero
    PATH configuration needed.
    """
    system32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    bat_path  = system32 / "cdp-dev.bat"

    bat_content = f'@echo off\n"{cdp_exe}" %*\n'

    print(f"  Writing wrapper: {bat_path}")
    print(f"  Points to     : {cdp_exe}")

    if not _is_admin():
        _relaunch_as_admin()

    try:
        bat_path.write_text(bat_content)
        print(f"  ✓  Installed cdp-dev.bat → {bat_path}")
        print()
        print("  cdp-dev is now available in EVERY terminal, immediately.")
        print("  No terminal restart needed.")
    except PermissionError:
        print(f"  ✗  Permission denied writing to {system32}")
        print("  Run this script as Administrator:")
        print("  Right-click terminal → Run as administrator → python bootstrap.py")
        sys.exit(1)


# ── Unix: add to shell rc file ────────────────────────────────────────────────

def fix_unix(scripts_dir: Path):
    scripts_str = str(scripts_dir)
    shell = os.environ.get("SHELL", "")
    home  = Path.home()

    if "zsh" in shell:
        rc = home / ".zshrc"
    elif "bash" in shell:
        rc = home / ".bash_profile" if platform.system() == "Darwin" else home / ".bashrc"
    else:
        rc = home / ".profile"

    content = rc.read_text() if rc.exists() else ""
    if scripts_str in content:
        print(f"  ✓  Already in {rc}")
        return

    with open(rc, "a") as f:
        f.write(f"\n# cdp-local-dev\nexport PATH=\"{scripts_str}:$PATH\"\n")

    os.environ["PATH"] = scripts_str + ":" + os.environ.get("PATH", "")
    print(f"  ✓  Added to {rc}")
    print(f"  Run: source {rc}  (or open a new terminal)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print("  CDP Local Dev — Bootstrap")
    print(f"  Python : {sys.executable}")
    print()

    exe = find_cdpdev_exe()

    if exe is None:
        print("  ✗  cdp-dev.exe not found.")
        print()
        print("  Install it first:")
        print("  pip install git+https://github.com/mrjoshuasamuel/cdp-local-dev.git")
        print()
        print("  Searched in:")
        for d in _candidate_dirs():
            print(f"    {d}")
        sys.exit(1)

    print(f"  ✓  Found: {exe}")
    print()

    if platform.system() == "Windows":
        install_bat_wrapper(exe)
    else:
        fix_unix(exe.parent)

    print()
    print("  ✓  Done! Run in this same terminal:  cdp-dev install")
    print()


if __name__ == "__main__":
    main()
