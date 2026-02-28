"""
kind_manager.py
Manages the Kind (Kubernetes in Docker) cluster lifecycle.
"""
import subprocess
import sys
import os
import platform
import importlib.resources
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

CLUSTER_NAME = "cdp-local"


def _run(cmd: list, check: bool = True, capture: bool = False, input_text: str = None) -> subprocess.CompletedProcess:
    """Run a shell command, streaming output unless capture=True."""
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
        input=input_text,
    )


def _helm_config_path() -> Path:
    """
    Resolve the helm/ directory whether the package is installed
    (importlib.resources) or running from a local editable install (src layout).
    """
    try:
        # Installed via pip — files live inside the package
        with importlib.resources.path("cdp_dev", "__init__.py") as p:
            candidate = p.parent.parent / "helm"
            if candidate.exists():
                return candidate
    except Exception:
        pass

    # Editable install or running from repo root
    here = Path(__file__).parent.parent
    candidate = here / "helm"
    if candidate.exists():
        return candidate

    raise FileNotFoundError(
        "Cannot locate helm/ directory. "
        "Make sure you installed the package correctly: "
        "pip install git+https://github.com/<org>/cdp-local-dev.git"
    )


def cluster_exists() -> bool:
    try:
        result = _run(["kind", "get", "clusters"], capture=True, check=False)
        return CLUSTER_NAME in result.stdout.splitlines()
    except Exception:
        return False


def cluster_running() -> bool:
    """Check if the Kind Docker container is actually running (not paused/stopped)."""
    try:
        result = _run(
            ["docker", "inspect", "--format", "{{.State.Running}}", f"{CLUSTER_NAME}-control-plane"],
            capture=True, check=False
        )
        return result.stdout.strip() == "true"
    except Exception:
        return False


def create_cluster():
    """Create the Kind cluster using our config file."""
    if cluster_exists():
        console.print(f"[yellow]⚠  Cluster '[bold]{CLUSTER_NAME}[/bold]' already exists — skipping create.[/yellow]")
        return

    # Prefer repo layout; fall back to installed-package layout
    base = Path(__file__).parent
    kind_config = base / "helm" / "kind" / "kind-config.yaml"
    if not kind_config.exists():
        kind_config = _helm_config_path() / "kind" / "kind-config.yaml"

    if not kind_config.exists():
        console.print(f"[red]  ✗  kind-config.yaml not found at {kind_config}[/red]")
        sys.exit(1)

    console.print(f"[cyan]  Using Kind config:[/cyan] {kind_config}")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  transient=True) as progress:
        progress.add_task("Creating Kind cluster (this takes ~60 seconds)...", total=None)
        _run(["kind", "create", "cluster", "--config", str(kind_config), "--name", CLUSTER_NAME])

    console.print(f"[green]  ✓  Kind cluster '[bold]{CLUSTER_NAME}[/bold]' created.[/green]")


def delete_cluster():
    """Delete the Kind cluster."""
    if not cluster_exists():
        console.print(f"[yellow]  Cluster '{CLUSTER_NAME}' does not exist.[/yellow]")
        return
    _run(["kind", "delete", "cluster", "--name", CLUSTER_NAME])
    console.print(f"[green]  ✓  Cluster '{CLUSTER_NAME}' deleted.[/green]")


def start_cluster():
    """Resume a stopped Kind cluster by starting its Docker containers."""
    if not cluster_exists():
        console.print("[red]  ✗  Cluster does not exist. Run [bold]cdp-dev install[/bold] first.[/red]")
        sys.exit(1)

    if cluster_running():
        console.print(f"[green]  ✓  Cluster '{CLUSTER_NAME}' is already running.[/green]")
        return

    console.print(f"[cyan]  Starting Kind cluster containers...[/cyan]")
    _run(["docker", "start", f"{CLUSTER_NAME}-control-plane"])
    console.print(f"[green]  ✓  Cluster '{CLUSTER_NAME}' started.[/green]")


def stop_cluster():
    """Pause the Kind cluster by stopping its Docker containers (data is preserved)."""
    if not cluster_exists():
        console.print("[yellow]  No cluster to stop.[/yellow]")
        return

    console.print(f"[cyan]  Stopping Kind cluster containers (your data is preserved)...[/cyan]")
    _run(["docker", "stop", f"{CLUSTER_NAME}-control-plane"], check=False)
    console.print(f"[green]  ✓  Cluster '{CLUSTER_NAME}' stopped.[/green]")


def get_kubeconfig():
    """Export kubeconfig so kubectl/helm point at the local cluster."""
    _run(["kind", "export", "kubeconfig", "--name", CLUSTER_NAME])
