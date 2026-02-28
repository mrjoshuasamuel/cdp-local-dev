"""
bootstrap.py
Run this ONCE after pip install to fix PATH automatically.

    python bootstrap.py

Works on Windows, macOS, and Linux.
Detects the correct Scripts directory for THIS machine and THIS user
automatically — no hardcoded paths.
"""
import os
import sys
import platform
import sysconfig
import subprocess
from pathlib import Path


def get_scripts_dir() -> Path:
    return Path(sysconfig.get_path("scripts"))


def main():
    scripts_dir = get_scripts_dir()
    cdp_dev_exe = scripts_dir / ("cdp-dev.exe" if platform.system() == "Windows" else "cdp-dev")

    print(f"\n  CDP Local Dev — Bootstrap")
    print(f"  Python     : {sys.executable}")
    print(f"  Scripts dir: {scripts_dir}")
    print(f"  cdp-dev    : {cdp_dev_exe}")
    print()

    if not cdp_dev_exe.exists():
        print("  ✗  cdp-dev not found. Install it first:")
        print("     pip install git+https://github.com/mrjoshuasamuel/cdp-local-dev.git")
        sys.exit(1)

    # ── Windows ────────────────────────────────────────────────────────────
    if platform.system() == "Windows":
        _fix_windows(scripts_dir)

    # ── macOS / Linux ──────────────────────────────────────────────────────
    else:
        _fix_unix(scripts_dir)

    print()
    print("  ✓  Done! You can now run:  cdp-dev install")
    print()


def _fix_windows(scripts_dir: Path):
    scripts_str = str(scripts_dir)

    # 1. Fix for this terminal session immediately
    os.environ["PATH"] = os.environ.get("PATH", "") + ";" + scripts_str

    # 2. Persist to Windows user PATH via registry
    try:
        import winreg
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

        if scripts_str.lower() not in current.lower():
            new_path = f"{current};{scripts_str}" if current else scripts_str
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
            print(f"  ✓  Added to Windows user PATH: {scripts_str}")
        else:
            print(f"  ✓  Already in PATH: {scripts_str}")

        winreg.CloseKey(key)

        # Broadcast WM_SETTINGCHANGE so new terminals pick it up without reboot
        import ctypes
        HWND_BROADCAST  = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", 2, 5000, None
        )

    except Exception as e:
        print(f"  ⚠  Could not write to registry: {e}")
        print(f"  Run this in PowerShell to fix it manually:")
        print(f'  [Environment]::SetEnvironmentVariable("Path", '
              f'[Environment]::GetEnvironmentVariable("Path","User") + '
              f'";{scripts_str}", "User")')


def _fix_unix(scripts_dir: Path):
    scripts_str = str(scripts_dir)

    # Detect which shell config file to update
    shell = os.environ.get("SHELL", "")
    home  = Path.home()

    if "zsh" in shell:
        rc_file = home / ".zshrc"
    elif "bash" in shell:
        rc_file = home / ".bashrc"
        # macOS uses .bash_profile
        if platform.system() == "Darwin" and not rc_file.exists():
            rc_file = home / ".bash_profile"
    else:
        rc_file = home / ".profile"

    export_line = f'\nexport PATH="{scripts_str}:$PATH"\n'
    marker      = f"# cdp-local-dev PATH"

    # Check if already added
    if rc_file.exists() and scripts_str in rc_file.read_text():
        print(f"  ✓  Already in {rc_file}")
        return

    # Append to shell config
    with open(rc_file, "a") as f:
        f.write(f"\n{marker}\n{export_line}")

    print(f"  ✓  Added to {rc_file}")
    print(f"  Run:  source {rc_file}  (or open a new terminal)")

    # Also fix current session
    os.environ["PATH"] = scripts_str + ":" + os.environ.get("PATH", "")


if __name__ == "__main__":
    main()
