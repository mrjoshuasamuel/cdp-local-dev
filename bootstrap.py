"""
bootstrap.py
Finds cdp-dev.exe wherever pip actually installed it on this machine
and adds it to PATH permanently.

Handles the Windows split-brain case where `python` and `pip` point
to different locations (Microsoft Store Python).
"""
import os
import sys
import site
import platform
import sysconfig
import subprocess
from pathlib import Path


def find_cdpdev() -> Path | None:
    """
    Search every plausible Scripts directory on this machine for cdp-dev.exe.
    Returns the Path if found, None if not installed yet.
    """
    candidates = set()

    # 1. Standard sysconfig scripts dir
    candidates.add(Path(sysconfig.get_path("scripts")))

    # 2. User-level scripts dir (where --user installs go)
    if hasattr(site, "getuserbase"):
        user_base = Path(site.getuserbase())
        if platform.system() == "Windows":
            candidates.add(user_base / "Scripts")
        else:
            candidates.add(user_base / "bin")

    # 3. site.getusersitepackages() parent
    if hasattr(site, "getusersitepackages"):
        usp = Path(site.getusersitepackages())
        # Walk up to find Scripts sibling
        for parent in [usp, usp.parent, usp.parent.parent]:
            if platform.system() == "Windows":
                candidates.add(parent / "Scripts")
            else:
                candidates.add(parent / "bin")

    # 4. Scan the Packages directory (Microsoft Store Python specific)
    if platform.system() == "Windows":
        packages_root = Path.home() / "AppData" / "Local" / "Packages"
        if packages_root.exists():
            for pkg_dir in packages_root.glob("PythonSoftwareFoundation.Python.*"):
                scripts = pkg_dir / "LocalCache" / "local-packages" / "Python311" / "Scripts"
                candidates.add(scripts)
                # Also try without version subfolder
                for sub in (pkg_dir / "LocalCache" / "local-packages").glob("Python*"):
                    candidates.add(sub / "Scripts")

    exe_name = "cdp-dev.exe" if platform.system() == "Windows" else "cdp-dev"

    for candidate in candidates:
        exe = candidate / exe_name
        if exe.exists():
            return exe

    return None


def main():
    print()
    print("  CDP Local Dev — Bootstrap")
    print(f"  Python : {sys.executable}")
    print()

    exe = find_cdpdev()

    if exe is None:
        print("  ✗  cdp-dev not found in any Scripts directory.")
        print()
        print("  Install it first:")
        print("     pip install git+https://github.com/mrjoshuasamuel/cdp-local-dev.git")
        print()
        print("  Searched directories:")
        # Show what we searched
        _print_searched()
        sys.exit(1)

    scripts_dir = exe.parent
    print(f"  ✓  Found cdp-dev: {exe}")
    print(f"  Scripts dir    : {scripts_dir}")
    print()

    if platform.system() == "Windows":
        _fix_windows(scripts_dir)
    else:
        _fix_unix(scripts_dir)

    print()
    print("  ✓  Done! Open a new terminal and run:  cdp-dev install")
    print()


def _print_searched():
    candidates = set()
    candidates.add(Path(sysconfig.get_path("scripts")))
    if hasattr(site, "getuserbase"):
        candidates.add(Path(site.getuserbase()) / "Scripts")
    if platform.system() == "Windows":
        packages_root = Path.home() / "AppData" / "Local" / "Packages"
        if packages_root.exists():
            for pkg_dir in packages_root.glob("PythonSoftwareFoundation.Python.*"):
                candidates.add(pkg_dir / "LocalCache" / "local-packages" / "Python311" / "Scripts")
    for c in sorted(candidates):
        print(f"     {c}")


def _fix_windows(scripts_dir: Path):
    scripts_str = str(scripts_dir)

    # Fix current session
    os.environ["PATH"] = os.environ.get("PATH", "") + ";" + scripts_str

    # Persist to user registry
    try:
        import winreg
        import ctypes

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, "Environment",
            0, winreg.KEY_READ | winreg.KEY_WRITE
        )
        try:
            current, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current = ""

        if scripts_str.lower() not in current.lower():
            new_path = f"{current};{scripts_str}" if current else scripts_str
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
            print(f"  ✓  Permanently added to Windows PATH: {scripts_str}")

            # Broadcast change so new terminals see it immediately
            HWND_BROADCAST   = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", 2, 5000, None
            )
        else:
            print(f"  ✓  Already in PATH: {scripts_str}")

        winreg.CloseKey(key)

    except Exception as e:
        print(f"  ⚠  Could not write to registry ({e})")
        print(f"  Run this in PowerShell manually:")
        print(f'  [Environment]::SetEnvironmentVariable("Path", '
              f'[Environment]::GetEnvironmentVariable("Path","User") + '
              f'";{scripts_str}", "User")')


def _fix_unix(scripts_dir: Path):
    scripts_str = str(scripts_dir)
    shell = os.environ.get("SHELL", "")
    home  = Path.home()

    if "zsh" in shell:
        rc_file = home / ".zshrc"
    elif "bash" in shell:
        rc_file = home / ".bash_profile" if platform.system() == "Darwin" else home / ".bashrc"
    else:
        rc_file = home / ".profile"

    content = rc_file.read_text() if rc_file.exists() else ""
    if scripts_str in content:
        print(f"  ✓  Already in {rc_file}")
        return

    with open(rc_file, "a") as f:
        f.write(f"\n# cdp-local-dev\nexport PATH=\"{scripts_str}:$PATH\"\n")

    os.environ["PATH"] = scripts_str + ":" + os.environ.get("PATH", "")
    print(f"  ✓  Added to {rc_file}")
    print(f"  Run: source {rc_file}")


if __name__ == "__main__":
    main()
