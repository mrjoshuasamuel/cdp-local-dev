"""
helm_manager.py — installs Airflow via Helm into the Kind cluster.
"""
import subprocess
import sys
import time
import yaml
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import box

console = Console()


def _run(cmd: list, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)


def _helm_dir() -> Path:
    """
    Locate helm/ directory — always inside the cdp_dev package itself
    so it works whether installed via pip or run from the repo.
    """
    # Inside the installed package (pip install)
    pkg_helm = Path(__file__).parent / "helm"
    if pkg_helm.exists():
        return pkg_helm

    # Repo root fallback (editable / dev mode)
    repo_helm = Path(__file__).parent.parent / "helm"
    if repo_helm.exists():
        return repo_helm

    raise FileNotFoundError(
        "Cannot locate helm/ directory. "
        "Reinstall: pip install --upgrade git+https://github.com/mrjoshuasamuel/cdp-local-dev.git"
    )


def _sanitize_airflow_values(values_path: Path):
    """Auto-fix known schema issues before passing values to Helm."""
    with open(values_path, "r") as f:
        values = yaml.safe_load(f)

    changed = False

    # Fix: webserver.service must be ClusterIP — port-forward handles access
    svc = values.get("webserver", {}).get("service", {})
    if svc.get("type") == "NodePort" or "nodePort" in svc or "ports" in svc:
        values.setdefault("webserver", {})["service"] = {"type": "ClusterIP"}
        changed = True
        console.print("[yellow]  ⚠  Fixed: webserver.service → ClusterIP[/yellow]")

    # Fix: Fernet key must be a real 32-byte base64 key
    if not _is_valid_fernet_key(values.get("fernetKey", "")):
        from cryptography.fernet import Fernet
        values["fernetKey"] = Fernet.generate_key().decode()
        changed = True
        console.print("[yellow]  ⚠  Fixed: generated valid Fernet key[/yellow]")

    if changed:
        with open(values_path, "w") as f:
            yaml.dump(values, f, default_flow_style=False, allow_unicode=True)


def _is_valid_fernet_key(key: str) -> bool:
    try:
        import base64
        return len(base64.urlsafe_b64decode(key.encode())) == 32
    except Exception:
        return False


def add_repos():
    console.print("[cyan]  Adding Helm repo: apache-airflow[/cyan]")
    _run(["helm", "repo", "add", "apache-airflow", "https://airflow.apache.org", "--force-update"])
    _run(["helm", "repo", "update"])
    console.print("[green]  ✓  Helm repos updated.[/green]")


def create_namespace(ns: str):
    result = _run(["kubectl", "get", "namespace", ns], check=False, capture=True)
    if result.returncode != 0:
        _run(["kubectl", "create", "namespace", ns])
        console.print(f"[green]  ✓  Namespace '{ns}' created.[/green]")
    else:
        console.print(f"[dim]  Namespace '{ns}' already exists.[/dim]")


def _get_pod_status(namespace: str) -> list:
    result = _run(
        ["kubectl", "get", "pods", "-n", namespace, "--no-headers",
         "-o", "custom-columns=NAME:.metadata.name,"
               "READY:.status.containerStatuses[0].ready,"
               "STATUS:.status.phase"],
        check=False, capture=True
    )
    pods = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            pods.append({"name": parts[0], "ready": parts[1], "status": parts[2]})
    return pods


def _wait_for_pods(namespace: str, timeout_seconds: int = 900):
    console.print()
    console.print(f"[cyan]  Waiting for pods (up to {timeout_seconds//60} min)...[/cyan]")
    console.print("  [dim]First run is slower — Docker is pulling ~1 GB of images.[/dim]")
    console.print()

    start     = time.time()
    last_print = 0

    while True:
        elapsed = int(time.time() - start)
        if elapsed > timeout_seconds:
            console.print("[red]  ✗  Pods did not become ready in time.[/red]")
            console.print("  [yellow]kubectl get pods -n airflow[/yellow]")
            console.print("  [yellow]kubectl describe pod <name> -n airflow[/yellow]")
            sys.exit(1)

        pods = _get_pod_status(namespace)

        if elapsed - last_print >= 30:
            status_str = "  ".join(
                f"{'✓' if p['ready'] == 'true' else '⏳'} {p['name'].replace('airflow-', '')}"
                for p in pods
            )
            console.print(f"  [{elapsed}s] {status_str}")
            last_print = elapsed

        if pods and all(p["ready"] == "true" for p in pods):
            console.print()
            console.print("[green]  ✓  All pods ready![/green]")
            _print_pod_table(namespace)
            return

        time.sleep(10)


def _print_pod_table(namespace: str):
    pods = _get_pod_status(namespace)
    if not pods:
        return
    table = Table(box=box.ROUNDED, show_lines=True)
    table.add_column("Pod",    style="cyan", no_wrap=True)
    table.add_column("Ready",  justify="center")
    table.add_column("Status", justify="center")
    for p in pods:
        table.add_row(
            p["name"].replace("airflow-", ""),
            "[green]✓[/green]" if p["ready"] == "true" else "[yellow]⏳[/yellow]",
            f"[green]{p['status']}[/green]" if p["status"] == "Running" else p["status"]
        )
    console.print(table)


def install_airflow():
    values_file = _helm_dir() / "values" / "airflow.yaml"

    console.print()
    console.print("[bold cyan]Installing Apache Airflow...[/bold cyan]")
    console.print(f"[dim]  Values: {values_file}[/dim]")

    _sanitize_airflow_values(values_file)
    create_namespace("airflow")

    cmd = [
        "helm", "upgrade", "--install", "airflow",
        "apache-airflow/airflow",
        "--namespace", "airflow",
        "--values",    str(values_file),
        "--timeout",   "15m",
    ]

    console.print("[cyan]  Running Helm install...[/cyan]")
    result = _run(cmd, check=False)

    if result.returncode != 0:
        console.print("[bold red]✗  Helm install failed.[/bold red]")
        console.print(result.stderr or result.stdout)
        sys.exit(1)

    console.print("[green]  ✓  Helm release created.[/green]")
    _wait_for_pods("airflow", timeout_seconds=900)


def uninstall_airflow():
    _run(["helm", "uninstall", "airflow", "--namespace", "airflow"], check=False)
    console.print("[green]  ✓  Airflow removed.[/green]")
