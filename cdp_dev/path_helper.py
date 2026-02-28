"""
path_helper.py
Makes cdp-dev accessible from any terminal on any OS.

Windows strategy: write cdp-dev.bat into C:\Windows\System32
  — always on PATH, no configuration, works immediately in every terminal.

macOS/Linux strategy: add Scripts dir to shell rc file.
"""
import os
import sys
import site
import platform
import sysconfig
import ctypes
from pathlib import Path


# ── Find where pip installed cdp-dev ─────────────────────────────────────────

def find_cdpdev_exe() -> Path | None:
    """Locate cdp-dev.exe/.sh regardless of Python installation type."""
    exe_name = "cdp-dev.exe" if platform.system() == "Windows" else "cdp-dev"
    for d in _candidate_dirs():
        exe = d / exe_name
        if exe.exists():
            return exe
    return None


def _candidate_dirs() -> list:
    dirs = []

    # Standard pip scripts location
    dirs.append(Path(sysconfig.get_path("scripts")))

    # pip --user install location
    if hasattr(site, "getuserbase"):
        base = Path(site.getuserbase())
        dirs.append(base / ("Scripts" if platform.system() == "Windows" else "bin"))

    # Microsoft Store Python: scan all versions under Packages
    if platform.system() == "Windows":
        packages = Path.home() / "AppData" / "Local" / "Packages"
        if packages.exists():
            for pkg in sorted(packages.glob("PythonSoftwareFoundation.Python.*"), reverse=True):
                local = pkg / "LocalCache" / "local-packages"
                if local.exists():
                    for py_ver in sorted(local.glob("Python*"), reverse=True):
                        dirs.append(py_ver / "Scripts")

    return dirs


def get_scripts_dir() -> Path:
    exe = find_cdpdev_exe()
    return exe.parent if exe else Path(sysconfig.get_path("scripts"))


def is_cdpdev_on_path() -> bool:
    import shutil
    return shutil.which("cdp-dev") is not None


# ── Windows: System32 .bat wrapper ───────────────────────────────────────────

def _bat_path() -> Path:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    return Path(system_root) / "System32" / "cdp-dev.bat"


def _bat_is_current(cdp_exe: Path) -> bool:
    bat = _bat_path()
    if not bat.exists():
        return False
    return str(cdp_exe) in bat.read_text()


def _is_admin_windows() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _install_bat_as_admin(cdp_exe: Path):
    """Relaunch current process with UAC to write the .bat file."""
    from rich.console import Console
    console = Console()
    console.print()
    console.print("[bold yellow]  One-time setup: installing cdp-dev system-wide...[/bold yellow]")
    console.print("  Windows will show a permission prompt — click [bold]Yes[/bold].")
    console.print()

    # Pass a special flag so the elevated process knows to just install bat and exit
    import subprocess
    script = (
        f"import sys; sys.path.insert(0, r'{Path(__file__).parent.parent}'); "
        f"from cdp_dev.path_helper import _write_bat; "
        f"_write_bat(r'{cdp_exe}')"
    )
    ret = ctypes.windll.shell32.ShellExecuteW(
        None, "runas",
        sys.executable,
        f'-c "{script}"',
        None, 1   # SW_SHOWNORMAL
    )
    if ret <= 32:
        console.print("[yellow]  ⚠  Could not auto-install. You can still use:[/yellow]")
        console.print("     [cyan]python -m cdp_dev <command>[/cyan]")


def _write_bat(cdp_exe_path: str):
    """Write the .bat file. Called in elevated process."""
    bat = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "cdp-dev.bat"
    bat.write_text(f'@echo off\n"{cdp_exe_path}" %*\n')


def _install_bat_windows(cdp_exe: Path):
    """Install cdp-dev.bat into System32 (with UAC if needed)."""
    if _bat_is_current(cdp_exe):
        return  # already installed and pointing to right exe

    if _is_admin_windows():
        _write_bat(str(cdp_exe))
    else:
        _install_bat_as_admin(cdp_exe)


# ── macOS / Linux: shell rc file ─────────────────────────────────────────────

def _fix_unix(scripts_dir: Path):
    scripts_str = str(scripts_dir)
    if scripts_str in os.environ.get("PATH", ""):
        return  # already active in this session

    shell = os.environ.get("SHELL", "")
    home  = Path.home()

    if "zsh" in shell:
        rc = home / ".zshrc"
    elif "bash" in shell:
        rc = home / ".bash_profile" if platform.system() == "Darwin" else home / ".bashrc"
    else:
        rc = home / ".profile"

    content = rc.read_text() if rc.exists() else ""
    if scripts_str not in content:
        with open(rc, "a") as f:
            f.write(f"\n# cdp-local-dev\nexport PATH=\"{scripts_str}:$PATH\"\n")

    # Fix current session
    os.environ["PATH"] = scripts_str + ":" + os.environ.get("PATH", "")


# ── Main public function ──────────────────────────────────────────────────────

_already_run = False

def ensure_cdpdev_globally_accessible():
    """
    Called automatically on every CLI invocation.
    On Windows: installs cdp-dev.bat into System32 (UAC prompt on first run).
    On macOS/Linux: adds Scripts dir to shell rc file.
    Silent if already set up correctly.
    """
    global _already_run
    if _already_run:
        return
    _already_run = True

    cdp_exe = find_cdpdev_exe()
    if cdp_exe is None:
        return  # package not properly installed, skip

    if platform.system() == "Windows":
        _install_bat_windows(cdp_exe)
    else:
        _fix_unix(cdp_exe.parent)


def ensure_on_path():
    """Legacy helper — kept for compatibility."""
    ensure_cdpdev_globally_accessible()
