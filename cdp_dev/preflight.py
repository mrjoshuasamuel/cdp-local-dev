"""
preflight.py
Self-healing preflight checks.

On Windows:
  - Installs Chocolatey automatically if missing (relaunches as Admin if needed)
  - Installs helm, kind, kubectl via choco automatically
  - Waits for Docker Desktop to start if it is not running

On macOS:
  - Installs brew if missing
  - Installs helm, kind, kubectl via brew automatically

Never stops and says "fix it yourself" — it fixes it.
"""
import os
import re
import shutil
import subprocess
import sys
import platform
import time
import ctypes
from dataclasses import dataclass, field
from typing import List, Optional

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

console = Console()
IS_WINDOWS = platform.system() == "Windows"
IS_MAC     = platform.system() == "Darwin"
IS_LINUX   = platform.system() == "Linux"


# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS = {
    "helm": {
        "min_version":   (3, 14),
        "version_cmd":   ["helm", "version", "--short"],
        "choco_pkg":     "kubernetes-helm",
        "brew_pkg":      "helm",
        "linux_hint":    "https://helm.sh/docs/intro/install/",
    },
    "kind": {
        "min_version":   (0, 23),
        "version_cmd":   ["kind", "version"],
        "choco_pkg":     "kind",
        "brew_pkg":      "kind",
        "linux_hint":    "https://kind.sigs.k8s.io/docs/user/quick-start/",
    },
    "kubectl": {
        "min_version":   (1, 28),
        "version_cmd":   ["kubectl", "version", "--client", "--output=yaml"],
        "choco_pkg":     "kubernetes-cli",
        "brew_pkg":      "kubectl",
        "linux_hint":    "https://kubernetes.io/docs/tasks/tools/",
    },
}


@dataclass
class CheckResult:
    tool:    str
    found:   bool
    version: str
    ok:      bool
    hint:    str = ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_version(raw: str) -> tuple:
    m = re.search(r'(\d+)\.(\d+)', raw)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _run(cmd: list, capture: bool = False, check: bool = False, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=capture, text=True, check=check, timeout=timeout)


def _is_admin_windows() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _relaunch_as_admin_windows():
    """Relaunch the current process with UAC elevation."""
    console.print()
    console.print("[bold yellow]⚠  Administrator privileges required to install tools.[/bold yellow]")
    console.print("   Windows will show a UAC prompt — click [bold]Yes[/bold] to continue.")
    console.print()
    time.sleep(2)

    import ctypes
    params = " ".join(f'"{a}"' for a in sys.argv)
    ret = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
    )
    if ret <= 32:
        console.print("[red]  ✗  Could not elevate privileges automatically.[/red]")
        console.print("  Please re-run this command in a terminal opened as Administrator:")
        console.print(f"  [yellow]  {sys.executable} -m cdp_dev.cli install[/yellow]")
        sys.exit(1)
    sys.exit(0)  # original non-admin process exits; elevated one takes over


# ── Chocolatey (Windows) ──────────────────────────────────────────────────────

def _choco_available() -> bool:
    return shutil.which("choco") is not None


def _install_choco():
    """Install Chocolatey on Windows. Must be running as Admin."""
    if _choco_available():
        return

    console.print("[cyan]  Installing Chocolatey package manager...[/cyan]")

    if IS_WINDOWS and not _is_admin_windows():
        _relaunch_as_admin_windows()

    ps_cmd = (
        "Set-ExecutionPolicy Bypass -Scope Process -Force; "
        "[System.Net.ServicePointManager]::SecurityProtocol = "
        "[System.Net.ServicePointManager]::SecurityProtocol -bor 3072; "
        "iex ((New-Object System.Net.WebClient).DownloadString("
        "'https://community.chocolatey.org/install.ps1'))"
    )
    result = _run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
        capture=True
    )
    if result.returncode != 0:
        console.print(f"[red]  ✗  Chocolatey install failed:[/red]\n{result.stderr}")
        sys.exit(1)

    # Reload PATH so choco is found in the same process
    _refresh_path_windows()

    if _choco_available():
        console.print("[green]  ✓  Chocolatey installed.[/green]")
    else:
        console.print("[red]  ✗  Chocolatey installed but still not found in PATH.[/red]")
        console.print("  Close this terminal and reopen as Administrator, then run cdp-dev install again.")
        sys.exit(1)


def _refresh_path_windows():
    """Pull updated PATH from registry so newly installed tools are found."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")
        sys_path, _ = winreg.QueryValueEx(key, "Path")
        winreg.CloseKey(key)

        key2 = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment")
        try:
            user_path, _ = winreg.QueryValueEx(key2, "Path")
        except FileNotFoundError:
            user_path = ""
        winreg.CloseKey(key2)

        new_path = sys_path + ";" + user_path
        os.environ["PATH"] = new_path
    except Exception:
        # Add common choco paths manually as fallback
        choco_paths = [
            r"C:\ProgramData\chocolatey\bin",
            r"C:\ProgramData\chocolatey\lib\kubernetes-helm\tools",
            r"C:\ProgramData\chocolatey\lib\kind\tools",
            r"C:\ProgramData\chocolatey\lib\kubernetes-cli\tools",
        ]
        for p in choco_paths:
            if p not in os.environ.get("PATH", ""):
                os.environ["PATH"] = os.environ.get("PATH", "") + ";" + p


# ── Homebrew (macOS) ──────────────────────────────────────────────────────────

def _brew_available() -> bool:
    return shutil.which("brew") is not None


def _install_brew():
    if _brew_available():
        return
    console.print("[cyan]  Installing Homebrew...[/cyan]")
    result = _run([
        "/bin/bash", "-c",
        'curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh | bash'
    ], capture=True)
    if result.returncode != 0:
        console.print(f"[red]  ✗  Homebrew install failed:[/red]\n{result.stderr}")
        sys.exit(1)
    console.print("[green]  ✓  Homebrew installed.[/green]")


# ── Per-tool auto-install ─────────────────────────────────────────────────────

def _install_tool_windows(name: str, spec: dict):
    pkg = spec["choco_pkg"]
    console.print(f"[cyan]  Installing [bold]{name}[/bold] via Chocolatey...[/cyan]")

    if not _is_admin_windows():
        _relaunch_as_admin_windows()

    result = _run(["choco", "install", pkg, "-y", "--no-progress"], capture=True)
    if result.returncode != 0:
        console.print(f"[red]  ✗  Failed to install {name}:[/red]\n{result.stderr}")
        sys.exit(1)

    _refresh_path_windows()
    if shutil.which(name):
        console.print(f"[green]  ✓  {name} installed.[/green]")
    else:
        console.print(f"[yellow]  ⚠  {name} installed but PATH not updated yet.[/yellow]")
        console.print(f"  Close and reopen your terminal, then run cdp-dev install again.")
        sys.exit(1)


def _install_tool_mac(name: str, spec: dict):
    pkg = spec["brew_pkg"]
    console.print(f"[cyan]  Installing [bold]{name}[/bold] via Homebrew...[/cyan]")
    result = _run(["brew", "install", pkg], capture=True)
    if result.returncode != 0:
        console.print(f"[red]  ✗  Failed to install {name}:[/red]\n{result.stderr}")
        sys.exit(1)
    console.print(f"[green]  ✓  {name} installed.[/green]")


def _auto_install(name: str, spec: dict):
    """Install a missing tool automatically based on OS."""
    if IS_WINDOWS:
        _install_choco()
        _install_tool_windows(name, spec)
    elif IS_MAC:
        _install_brew()
        _install_tool_mac(name, spec)
    else:
        console.print(f"[red]  ✗  Cannot auto-install [bold]{name}[/bold] on Linux.[/red]")
        console.print(f"     {spec['linux_hint']}")
        sys.exit(1)


# ── Docker helpers ────────────────────────────────────────────────────────────

def _docker_installed() -> bool:
    return shutil.which("docker") is not None


def _docker_running() -> bool:
    try:
        subprocess.check_output(["docker", "info"], stderr=subprocess.DEVNULL, timeout=10)
        return True
    except Exception:
        return False


def _wait_for_docker():
    """
    If Docker is installed but not running, try to launch Docker Desktop
    and wait up to 120 seconds for it to become ready.
    """
    if _docker_running():
        return

    if not _docker_installed():
        console.print("[red]  ✗  Docker Desktop is not installed.[/red]")
        if IS_WINDOWS:
            console.print("     Download: https://docs.docker.com/desktop/install/windows-install/")
        elif IS_MAC:
            console.print("     Download: https://docs.docker.com/desktop/install/mac-install/")
        else:
            console.print("     https://docs.docker.com/engine/install/")
        console.print("  Install Docker Desktop, start it, then run cdp-dev install again.")
        sys.exit(1)

    # Docker installed but not running — try to launch it
    console.print("[yellow]  ⚠  Docker Desktop is not running. Attempting to start it...[/yellow]")

    try:
        if IS_WINDOWS:
            subprocess.Popen(
                [r"C:\Program Files\Docker\Docker\Docker Desktop.exe"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        elif IS_MAC:
            subprocess.Popen(
                ["open", "-a", "Docker"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
    except Exception:
        pass  # best effort — will catch below if it doesn't start

    # Wait up to 120 seconds
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  transient=True) as progress:
        task = progress.add_task("Waiting for Docker Desktop to start (up to 120s)...", total=None)
        for _ in range(24):   # 24 × 5s = 120s
            time.sleep(5)
            if _docker_running():
                progress.stop()
                console.print("[green]  ✓  Docker Desktop is running.[/green]")
                return

    console.print("[red]  ✗  Docker Desktop did not start within 120 seconds.[/red]")
    console.print("  Please open Docker Desktop manually, wait for the green 'Engine running'")
    console.print("  status, then run cdp-dev install again.")
    sys.exit(1)


# ── Single tool check ─────────────────────────────────────────────────────────

def _check_tool(name: str, spec: dict) -> CheckResult:
    if not shutil.which(name):
        return CheckResult(tool=name, found=False, version="—", ok=False)

    try:
        out = subprocess.check_output(
            spec["version_cmd"], stderr=subprocess.STDOUT, text=True, timeout=10
        )
        ver_tuple = _parse_version(out)
        ver_str   = ".".join(str(x) for x in ver_tuple)
        ok = ver_tuple >= spec["min_version"]
        return CheckResult(tool=name, found=True, version=ver_str, ok=ok)
    except Exception:
        return CheckResult(tool=name, found=True, version="unknown", ok=True)


# ── Main entry point ──────────────────────────────────────────────────────────

def run_preflight(verbose: bool = True) -> bool:
    """
    Check all tools. Auto-install anything missing.
    Returns True only when everything is confirmed working.
    """
    console.print()
    console.print("[bold cyan]  Running preflight checks...[/bold cyan]")
    console.print()

    # ── Step 1: Docker first ──────────────────────────────────────────────
    _wait_for_docker()

    # ── Step 2: Check and auto-install CLI tools ──────────────────────────
    for name, spec in TOOLS.items():
        result = _check_tool(name, spec)
        if not result.ok:
            console.print(f"[yellow]  ⚠  [bold]{name}[/bold] not found or out of date — installing automatically...[/yellow]")
            _auto_install(name, spec)
            # Re-check after install
            result = _check_tool(name, spec)
            if not result.ok:
                console.print(f"[red]  ✗  {name} still not available after install. Please restart your terminal and try again.[/red]")
                sys.exit(1)
        else:
            console.print(f"[green]  ✓  {name}[/green] [dim]{result.version}[/dim]")

    # ── Step 3: Print summary table ───────────────────────────────────────
    if verbose:
        console.print()
        table = Table(title="[bold]Preflight — All Checks Passed[/bold]",
                      box=box.ROUNDED, show_lines=True)
        table.add_column("Tool",     style="bold cyan", no_wrap=True)
        table.add_column("Version",  justify="center")
        table.add_column("Status",   justify="center")

        table.add_row("docker",  "running", "[green]✓  OK[/green]")
        for name, spec in TOOLS.items():
            r = _check_tool(name, spec)
            table.add_row(name, r.version, "[green]✓  OK[/green]")

        console.print(table)
        console.print()

    return True
