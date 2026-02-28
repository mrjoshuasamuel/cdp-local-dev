"""
helm_manager.py
Manages Helm chart installations inside the Kind cluster.
Phase 1: Airflow only.
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


def _helm_values_dir() -> Path:
    candidate = Path(__file__).parent.parent / "helm" / "values"
    if candidate.exists():
        return candidate
    candidate2 = Path(__file__).parent.parent.parent / "helm" / "values"
    if candidate2.exists():
        return candidate2
    raise FileNotFoundError("Cannot locate helm/values/ directory.")


def _sanitize_airflow_values(values_path: Path):
    """
    Auto-fix known schema issues in airflow.yaml before passing to Helm.
    Also ensures the Fernet key is a real valid key, not a placeholder.
    """
    with open(values_path, "r") as f:
        values = yaml.safe_load(f)

    changed = False

    # ── Fix 1: webserver.service — use ClusterIP (port-forward handles access)
    svc = values.get("webserver", {}).get("service", {})
    if svc.get("type") == "NodePort" or "nodePort" in svc or "ports" in svc:
        values.setdefault("webserver", {})["service"] = {"type": "ClusterIP"}
        changed = True
        console.print("[yellow]  ⚠  Fixed: webserver.service → ClusterIP[/yellow]")

    # ── Fix 2: Fernet key — must be a real 32-byte URL-safe base64 key
    fernet_key = values.get("fernetKey", "")
    if not _is_valid_fernet_key(fernet_key):
        from cryptography.fernet import Fernet
        values["fernetKey"] = Fernet.generate_key().decode()
        changed = True
        console.print("[yellow]  ⚠  Fixed: generated a valid Fernet key[/yellow]")

    if changed:
        with open(values_path, "w") as f:
            yaml.dump(values, f, default_flow_style=False, allow_unicode=True)


def _is_valid_fernet_key(key: str) -> bool:
    try:
        import base64
        decoded = base64.urlsafe_b64decode(key.encode())
        return len(decoded) == 32
    except Exception:
        return False


def add_repos():
    repos = {"apache-airflow": "https://airflow.apache.org"}
    for name, url in repos.items():
        console.print(f"[cyan]  Adding Helm repo:[/cyan] {name}")
        _run(["helm", "repo", "add", name, url, "--force-update"])
    _run(["helm", "repo", "update"])
    console.print("[green]  ✓  Helm repos updated.[/green]")


def create_namespace(ns: str):
    result = _run(["kubectl", "get", "namespace", ns], check=False, capture=True)
    if result.returncode != 0:
        _run(["kubectl", "create", "namespace", ns])
        console.print(f"[green]  ✓  Namespace '[bold]{ns}[/bold]' created.[/green]")
    else:
        console.print(f"[dim]  Namespace '{ns}' already exists.[/dim]")


def _get_pod_status(namespace: str) -> list:
    """Return list of (name, ready, status) for all pods in namespace."""
    result = _run(
        ["kubectl", "get", "pods", "-n", namespace,
         "--no-headers",
         "-o", "custom-columns=NAME:.metadata.name,READY:.status.containerStatuses[0].ready,STATUS:.status.phase"],
        check=False, capture=True
    )
    pods = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            pods.append({"name": parts[0], "ready": parts[1], "status": parts[2]})
    return pods


def _wait_for_pods(namespace: str, timeout_seconds: int = 900):
    """
    Wait for all pods in namespace to be Running and Ready.
    Shows live pod status while waiting.
    Times out after timeout_seconds (default 15 min).
    """
    console.print()
    console.print(f"[cyan]  Waiting for Airflow pods to become ready (up to {timeout_seconds//60} minutes)...[/cyan]")
    console.print(f"  [dim]Note: First run takes longer — Docker is pulling ~1 GB of images.[/dim]")
    console.print()

    start = time.time()
    last_print = 0

    while True:
        elapsed = int(time.time() - start)

        if elapsed > timeout_seconds:
            console.print()
            console.print("[red]  ✗  Pods did not become ready in time.[/red]")
            _print_pod_table(namespace)
            console.print()
            console.print("  [dim]Check pod logs for errors:[/dim]")
            console.print("  [yellow]kubectl get pods -n airflow[/yellow]")
            console.print("  [yellow]kubectl describe pod <pod-name> -n airflow[/yellow]")
            sys.exit(1)

        pods = _get_pod_status(namespace)

        # Print status every 30 seconds
        if elapsed - last_print >= 30:
            console.print(f"  [{elapsed}s] Pods: ", end="")
            for p in pods:
                icon = "✓" if p["ready"] == "true" else "⏳"
                short_name = p["name"].replace("airflow-", "")
                console.print(f"{icon} {short_name}  ", end="")
            console.print()
            last_print = elapsed

        # Check if all pods are ready
        if pods and all(p["ready"] == "true" for p in pods):
            console.print()
            console.print("[green]  ✓  All Airflow pods are ready![/green]")
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
        ready_fmt  = "[green]✓[/green]" if p["ready"] == "true" else "[yellow]⏳[/yellow]"
        status_fmt = (
            "[green]Running[/green]"  if p["status"] == "Running"  else
            "[cyan]Pending[/cyan]"    if p["status"] == "Pending"  else
            f"[red]{p['status']}[/red]"
        )
        table.add_row(p["name"].replace("airflow-", ""), ready_fmt, status_fmt)
    console.print(table)


def install_airflow():
    values_file = _helm_values_dir() / "airflow.yaml"

    console.print()
    console.print("[bold cyan]Installing Apache Airflow...[/bold cyan]")
    console.print(f"[dim]  Values: {values_file}[/dim]")

    # Auto-fix values before running helm
    _sanitize_airflow_values(values_file)

    create_namespace("airflow")

    # Install without --wait — we poll ourselves with better feedback
    cmd = [
        "helm", "upgrade", "--install", "airflow",
        "apache-airflow/airflow",
        "--namespace", "airflow",
        "--values",    str(values_file),
        "--timeout",   "15m",
        # No --wait here — we handle waiting ourselves below
    ]

    console.print("[cyan]  Running Helm install...[/cyan]")
    result = _run(cmd, check=False)

    if result.returncode != 0:
        console.print()
        console.print("[bold red]✗  Helm install command failed.[/bold red]")
        console.print(result.stderr or result.stdout)
        sys.exit(1)

    console.print("[green]  ✓  Helm release created.[/green]")

    # Now wait for pods ourselves with live feedback
    _wait_for_pods("airflow", timeout_seconds=900)


def uninstall_airflow():
    _run(["helm", "uninstall", "airflow", "--namespace", "airflow"], check=False)
    console.print("[green]  ✓  Airflow removed.[/green]")
