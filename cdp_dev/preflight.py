"""
preflight.py
Checks that every required tool is available on the developer's machine
before the CLI tries to do anything. Gives clear, actionable error messages.
"""
import shutil
import subprocess
import sys
import platform
from dataclasses import dataclass
from typing import List

from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

TOOLS = {
    "docker": {
        "min_version": (24, 0),
        "version_cmd": ["docker", "version", "--format", "{{.Server.Version}}"],
        "install_hint": {
            "Darwin":  "https://docs.docker.com/desktop/install/mac-install/",
            "Linux":   "https://docs.docker.com/engine/install/",
            "Windows": "https://docs.docker.com/desktop/install/windows-install/",
        },
    },
    "kubectl": {
        "min_version": (1, 28),
        "version_cmd": ["kubectl", "version", "--client", "--output=yaml"],
        "install_hint": {
            "Darwin":  "brew install kubectl",
            "Linux":   "https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/",
            "Windows": "choco install kubernetes-cli",
        },
        "auto_install": True,
    },
    "helm": {
        "min_version": (3, 14),
        "version_cmd": ["helm", "version", "--short"],
        "install_hint": {
            "Darwin":  "brew install helm",
            "Linux":   "https://helm.sh/docs/intro/install/",
            "Windows": "choco install kubernetes-helm",
        },
        "auto_install": True,
    },
    "kind": {
        "min_version": (0, 23),
        "version_cmd": ["kind", "version"],
        "install_hint": {
            "Darwin":  "brew install kind",
            "Linux":   "https://kind.sigs.k8s.io/docs/user/quick-start/#installation",
            "Windows": "choco install kind",
        },
        "auto_install": True,
    },
}

@dataclass
class CheckResult:
    tool:    str
    found:   bool
    version: str
    ok:      bool
    hint:    str


def _parse_version(raw: str) -> tuple:
    """Extract (major, minor) from a raw version string."""
    import re
    m = re.search(r'(\d+)\.(\d+)', raw)
    if m:
        return int(m.group(1)), int(m.group(2))
    return (0, 0)


def _check_tool(name: str, spec: dict) -> CheckResult:
    os_name = platform.system()
    hint = spec["install_hint"].get(os_name, spec["install_hint"].get("Linux", ""))

    if not shutil.which(name):
        return CheckResult(tool=name, found=False, version="—", ok=False, hint=hint)

    try:
        out = subprocess.check_output(
            spec["version_cmd"], stderr=subprocess.STDOUT, text=True, timeout=10
        )
        ver_tuple = _parse_version(out)
        ver_str   = ".".join(str(x) for x in ver_tuple)
        ok = ver_tuple >= spec["min_version"]
        return CheckResult(tool=name, found=True, version=ver_str, ok=ok, hint=hint if not ok else "")
    except Exception:
        return CheckResult(tool=name, found=True, version="unknown", ok=True, hint="")


def _check_docker_running() -> bool:
    try:
        subprocess.check_output(["docker", "info"], stderr=subprocess.DEVNULL, timeout=10)
        return True
    except Exception:
        return False


def run_preflight(verbose: bool = True) -> bool:
    """
    Run all preflight checks.
    Returns True if all required tools are present and running, False otherwise.
    """
    results: List[CheckResult] = []

    for name, spec in TOOLS.items():
        results.append(_check_tool(name, spec))

    # special check — docker daemon running
    docker_running = _check_docker_running()

    if verbose:
        table = Table(title="[bold]CDP Local Dev — Preflight Check[/bold]",
                      box=box.ROUNDED, show_lines=True)
        table.add_column("Tool",        style="bold cyan",  no_wrap=True)
        table.add_column("Found",       justify="center")
        table.add_column("Version",     justify="center")
        table.add_column("Required",    justify="center", style="dim")
        table.add_column("Status",      justify="center")

        min_versions = {n: ".".join(str(x) for x in s["min_version"]) for n, s in TOOLS.items()}

        for r in results:
            found_icon   = "✓" if r.found else "✗"
            found_style  = "green" if r.found else "red"
            status_icon  = "[green]✓  OK[/green]" if r.ok else "[red]✗  FAIL[/red]"
            table.add_row(
                r.tool,
                f"[{found_style}]{found_icon}[/{found_style}]",
                r.version,
                f">= {min_versions[r.tool]}",
                status_icon,
            )

        # Docker daemon row
        d_style = "green" if docker_running else "red"
        d_icon  = "✓  Running" if docker_running else "✗  Not running"
        table.add_row("docker daemon", f"[{d_style}]{'✓' if docker_running else '✗'}[/{d_style}]",
                      "—", "running", f"[{d_style}]{d_icon}[/{d_style}]")

        console.print()
        console.print(table)
        console.print()

    all_ok = all(r.ok for r in results) and docker_running

    if not all_ok and verbose:
        console.print("[bold red]Some checks failed. Fix the issues above before running cdp-dev install.[/bold red]")
        console.print()
        for r in results:
            if not r.ok:
                console.print(f"  [yellow]→  {r.tool}:[/yellow] {r.hint}")
        if not docker_running:
            console.print(f"  [yellow]→  Docker daemon:[/yellow] Start Docker Desktop and try again.")
        console.print()

    return all_ok
