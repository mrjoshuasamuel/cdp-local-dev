"""
preflight.py
Self-healing preflight checks for the Docker Compose-based stack.

Responsibilities:
  - Make sure Docker is installed and running (start Docker Desktop if needed).
  - Make sure `docker compose` V2 is available.  Fall back to legacy `docker-compose`
    when that's all that's installed.
  - Nothing else.  Kind/Helm/kubectl are no longer required.

The _install_brew / _install_choco helpers are kept for future use but only
invoked as a last resort when Docker itself needs installing.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

from . import compose_manager
from .utils import IS_WINDOWS, IS_MAC, IS_LINUX, is_admin_windows

console = Console()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(cmd: list, capture: bool = False, check: bool = False, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=capture, text=True, check=check, timeout=timeout)


# ── Apple Silicon Rosetta detection ──────────────────────────────────────────

def _is_rosetta_translated() -> bool:
    """
    Return True when the current Python process is running under Rosetta 2.

    `platform.machine()` lies under Rosetta (returns x86_64 on Apple Silicon
    hardware), so we use sysctl.proc_translated which is truthful.
    """
    if not IS_MAC:
        return False
    try:
        out = subprocess.check_output(
            ["sysctl", "-n", "sysctl.proc_translated"],
            stderr=subprocess.DEVNULL, text=True, timeout=5,
        ).strip()
    except Exception:
        return False
    return out == "1"


def _brew_cmd() -> list[str]:
    """
    Return the argv prefix to invoke brew.  On Apple Silicon hardware running
    an x86_64 Python (Rosetta), prepend `arch -arm64` so brew targets the ARM
    Homebrew prefix at /opt/homebrew.
    """
    if not IS_MAC:
        return ["brew"]

    arm_brew = Path("/opt/homebrew/bin/brew")
    intel_brew = Path("/usr/local/bin/brew")

    if arm_brew.exists() and _is_rosetta_translated():
        return ["arch", "-arm64", str(arm_brew)]
    if arm_brew.exists():
        return [str(arm_brew)]
    if intel_brew.exists():
        return [str(intel_brew)]
    return ["brew"]


# ── Homebrew (macOS) — kept for potential future brew-based installs ─────────

def _brew_available() -> bool:
    return shutil.which("brew") is not None or Path("/opt/homebrew/bin/brew").exists()


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


# ── Chocolatey (Windows) — kept for future Windows installs ──────────────────

def _choco_available() -> bool:
    return shutil.which("choco") is not None


def _relaunch_as_admin_windows():
    """Relaunch the current process with UAC elevation."""
    import ctypes

    console.print()
    console.print("[bold yellow]⚠  Administrator privileges required.[/bold yellow]")
    console.print("   Windows will show a UAC prompt — click [bold]Yes[/bold] to continue.")
    console.print()
    time.sleep(2)

    params = " ".join(f'"{a}"' for a in sys.argv)
    ret = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
    )
    if ret <= 32:
        console.print("[red]  ✗  Could not elevate privileges automatically.[/red]")
        console.print("  Please re-run this command in an Administrator terminal.")
        sys.exit(1)
    sys.exit(0)


def _install_choco():
    if _choco_available():
        return
    console.print("[cyan]  Installing Chocolatey package manager...[/cyan]")
    if IS_WINDOWS and not is_admin_windows():
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
    if _choco_available():
        console.print("[green]  ✓  Chocolatey installed.[/green]")


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
    """If Docker is installed but not running, try to launch it and wait ~2 min."""
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
        console.print("  Install Docker, start it, then re-run cdp-dev install.")
        sys.exit(1)

    console.print("[yellow]  ⚠  Docker is not running.  Attempting to start it...[/yellow]")
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
        pass

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  transient=True) as progress:
        progress.add_task("Waiting for Docker to start (up to 120s)...", total=None)
        for _ in range(24):
            time.sleep(5)
            if _docker_running():
                progress.stop()
                console.print("[green]  ✓  Docker is running.[/green]")
                return

    console.print("[red]  ✗  Docker did not start within 120 seconds.[/red]")
    console.print("  Start Docker manually, then re-run cdp-dev install.")
    sys.exit(1)


# ── Docker Compose detection ─────────────────────────────────────────────────

def _detect_compose() -> list[str]:
    """
    Prefer `docker compose` (V2, plugin).  Fall back to legacy `docker-compose`
    (V1 standalone binary) if that's all that's installed.
    """
    try:
        r = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if r.returncode == 0:
            return ["docker", "compose"]
    except Exception:
        pass

    if shutil.which("docker-compose"):
        return ["docker-compose"]

    console.print("[red]  ✗  Docker Compose not found.[/red]")
    if IS_LINUX:
        console.print("     Install the docker-compose-plugin: "
                      "https://docs.docker.com/compose/install/linux/")
    else:
        console.print("     Update Docker Desktop — Compose V2 ships by default.")
    sys.exit(1)


# ── Main entry point ──────────────────────────────────────────────────────────

def run_preflight(verbose: bool = True) -> bool:
    """Verify Docker + docker compose are ready.  Returns True on success."""
    console.print()
    console.print("[bold cyan]  Running preflight checks...[/bold cyan]")
    console.print()

    _wait_for_docker()

    compose_cmd = _detect_compose()
    compose_manager.set_compose_cmd(compose_cmd)
    console.print(
        f"[green]  ✓  docker compose[/green] "
        f"[dim]({' '.join(compose_cmd)})[/dim]"
    )

    if verbose:
        console.print()
        table = Table(title="[bold]Preflight — All Checks Passed[/bold]",
                      box=box.ROUNDED, show_lines=True)
        table.add_column("Component", style="bold cyan", no_wrap=True)
        table.add_column("Status",    justify="center")
        table.add_row("docker",         "[green]✓  running[/green]")
        table.add_row(" ".join(compose_cmd), "[green]✓  available[/green]")
        console.print(table)
        console.print()

    return True
