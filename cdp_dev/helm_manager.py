"""
helm_manager.py
Manages Helm chart installations inside the Kind cluster.
Phase 1: Airflow only.
"""
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def _run(cmd: list, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)


def _helm_values_dir() -> Path:
    """Locate the helm/values/ directory regardless of install method."""
    # Running from repo / editable install
    candidate = Path(__file__).parent.parent / "helm" / "values"
    if candidate.exists():
        return candidate

    raise FileNotFoundError(
        "Cannot locate helm/values/ directory. "
        "Reinstall with: pip install git+https://github.com/<org>/cdp-local-dev.git"
    )


def add_repos():
    """Add the Helm repos we need (idempotent)."""
    repos = {
        "apache-airflow": "https://airflow.apache.org",
    }
    for name, url in repos.items():
        console.print(f"[cyan]  Adding Helm repo:[/cyan] {name}")
        _run(["helm", "repo", "add", name, url, "--force-update"])
    _run(["helm", "repo", "update"])
    console.print("[green]  ✓  Helm repos updated.[/green]")


def create_namespace(ns: str):
    """Create a Kubernetes namespace if it doesn't already exist."""
    result = _run(
        ["kubectl", "get", "namespace", ns],
        check=False, capture=True
    )
    if result.returncode != 0:
        _run(["kubectl", "create", "namespace", ns])
        console.print(f"[green]  ✓  Namespace '[bold]{ns}[/bold]' created.[/green]")
    else:
        console.print(f"[yellow]  ⚠  Namespace '{ns}' already exists.[/yellow]")


def install_airflow():
    """Install or upgrade Apache Airflow using our local values file."""
    values_file = _helm_values_dir() / "airflow.yaml"

    console.print()
    console.print("[bold cyan]Installing Apache Airflow...[/bold cyan]")
    console.print(f"[dim]  Values: {values_file}[/dim]")

    create_namespace("airflow")

    cmd = [
        "helm", "upgrade", "--install", "airflow",
        "apache-airflow/airflow",
        "--namespace",  "airflow",
        "--values",     str(values_file),
        "--timeout",    "10m",
        "--wait",
    ]

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  transient=True) as progress:
        progress.add_task(
            "Deploying Airflow pods (this can take 3–5 minutes on first run)...",
            total=None
        )
        result = _run(cmd, check=False)

    if result.returncode != 0:
        console.print()
        console.print("[bold red]✗  Airflow installation failed.[/bold red]")
        console.print("[dim]Run the command below for detailed output:[/dim]")
        console.print(f"[yellow]  {' '.join(cmd)}[/yellow]")
        sys.exit(1)

    console.print("[green]  ✓  Airflow installed successfully.[/green]")


def uninstall_airflow():
    """Remove the Airflow Helm release."""
    _run(["helm", "uninstall", "airflow", "--namespace", "airflow"], check=False)
    console.print("[green]  ✓  Airflow removed.[/green]")
