"""
helm_manager.py — installs Airflow via Helm into the Kind cluster.
Helm only creates resources — we watch and report progress ourselves.
"""
import subprocess
import sys
import time
import yaml
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()

AIRFLOW_CHART_VERSION = "1.15.0"
AIRFLOW_IMAGE_TAG     = "2.9.3"


def _run(cmd: list, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)


def _helm_dir() -> Path:
    pkg = Path(__file__).parent / "helm"
    if pkg.exists():
        return pkg
    repo = Path(__file__).parent.parent / "helm"
    if repo.exists():
        return repo
    raise FileNotFoundError("Cannot locate helm/ directory. Reinstall cdp-local-dev.")


def _sanitize_airflow_values(values_path: Path):
    with open(values_path, "r") as f:
        values = yaml.safe_load(f)
    changed = False

    svc = values.get("webserver", {}).get("service", {})
    if svc.get("type") == "NodePort" or "nodePort" in svc or "ports" in svc:
        values.setdefault("webserver", {})["service"] = {"type": "ClusterIP"}
        changed = True
        console.print("[yellow]  ⚠  Fixed: webserver.service → ClusterIP[/yellow]")

    if not _is_valid_fernet_key(values.get("fernetKey", "")):
        from cryptography.fernet import Fernet
        values["fernetKey"] = Fernet.generate_key().decode()
        changed = True
        console.print("[yellow]  ⚠  Fixed: generated valid Fernet key[/yellow]")

    # Always pin image tag
    values.setdefault("images", {}).setdefault("airflow", {})
    values["images"]["airflow"]["repository"] = "apache/airflow"
    values["images"]["airflow"]["tag"]        = AIRFLOW_IMAGE_TAG
    values["images"]["airflow"]["pullPolicy"] = "IfNotPresent"
    changed = True

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
    _run(["helm", "repo", "add", "apache-airflow",
          "https://airflow.apache.org", "--force-update"])
    _run(["helm", "repo", "update"])
    console.print("[green]  ✓  Helm repos updated.[/green]")


def create_namespace(ns: str):
    result = _run(["kubectl", "get", "namespace", ns], check=False, capture=True)
    if result.returncode != 0:
        _run(["kubectl", "create", "namespace", ns])
        console.print(f"[green]  ✓  Namespace '{ns}' created.[/green]")
    else:
        console.print(f"[dim]  Namespace '{ns}' already exists.[/dim]")


# ── Live progress display ──────────────────────────────────────────────────────

def _get_pods(namespace: str) -> list:
    result = _run(
        ["kubectl", "get", "pods", "-n", namespace, "--no-headers",
         "-o", "custom-columns="
               "NAME:.metadata.name,"
               "READY:.status.containerStatuses[0].ready,"
               "STATUS:.status.phase,"
               "RESTARTS:.status.containerStatuses[0].restartCount"],
        check=False, capture=True
    )
    pods = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            pods.append({
                "name":     parts[0],
                "ready":    parts[1] if len(parts) > 1 else "false",
                "status":   parts[2] if len(parts) > 2 else "Unknown",
                "restarts": parts[3] if len(parts) > 3 else "0",
            })
    return pods


def _get_jobs(namespace: str) -> list:
    result = _run(
        ["kubectl", "get", "jobs", "-n", namespace, "--no-headers",
         "-o", "custom-columns="
               "NAME:.metadata.name,"
               "COMPLETIONS:.status.succeeded,"
               "STATUS:.status.conditions[0].type"],
        check=False, capture=True
    )
    jobs = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if parts:
            jobs.append({
                "name":       parts[0],
                "succeeded":  parts[1] if len(parts) > 1 else "0",
                "condition":  parts[2] if len(parts) > 2 else "InProgress",
            })
    return jobs


def _build_progress_table(namespace: str, elapsed: int) -> Panel:
    pods = _get_pods(namespace)
    jobs = _get_jobs(namespace)

    table = Table(box=box.SIMPLE, show_header=True, expand=True)
    table.add_column("Component",  style="cyan",  no_wrap=True, min_width=35)
    table.add_column("Status",     justify="center", min_width=12)
    table.add_column("Ready",      justify="center", min_width=8)
    table.add_column("Restarts",   justify="center", min_width=8)

    # Jobs first (migrations run before pods start)
    for j in jobs:
        done = j["condition"] == "Complete" or j["succeeded"] not in ("0", "<none>", "")
        status_fmt  = "[green]✓  Complete[/green]" if done else "[yellow]⏳ Running[/yellow]"
        ready_fmt   = "[green]✓[/green]"            if done else "[dim]—[/dim]"
        short       = j["name"].replace("airflow-", "")
        table.add_row(f"[dim]{short}[/dim]", status_fmt, ready_fmt, "—")

    # Pods
    for p in pods:
        short    = p["name"].replace("airflow-", "")
        status   = p["status"]
        ready    = p["ready"]
        restarts = p["restarts"]

        if status == "Running" and ready == "true":
            status_fmt = "[green]✓  Running[/green]"
            ready_fmt  = "[green]✓[/green]"
        elif status == "Running":
            status_fmt = "[cyan]⏳ Starting[/cyan]"
            ready_fmt  = "[yellow]⏳[/yellow]"
        elif status == "Pending":
            status_fmt = "[yellow]⏳ Pending[/yellow]"
            ready_fmt  = "[dim]—[/dim]"
        elif status == "Succeeded":
            status_fmt = "[green]✓  Done[/green]"
            ready_fmt  = "[green]✓[/green]"
        else:
            status_fmt = f"[red]{status}[/red]"
            ready_fmt  = "[red]✗[/red]"

        restart_fmt = f"[red]{restarts}[/red]" if restarts not in ("0", "<none>", "") else "[dim]0[/dim]"
        table.add_row(short, status_fmt, ready_fmt, restart_fmt)

    mins, secs = divmod(elapsed, 60)
    title = (
        f"[bold cyan]Airflow — Starting up[/bold cyan]  "
        f"[dim]{mins:02d}:{secs:02d} elapsed  "
        f"(first run ~5 min while Docker pulls images)[/dim]"
    )
    return Panel(table, title=title, border_style="cyan")


def _all_ready(namespace: str) -> bool:
    """Returns True when all pods are Running+Ready and all jobs are Complete."""
    pods = _get_pods(namespace)
    jobs = _get_jobs(namespace)

    if not pods:
        return False

    # Need at least webserver, scheduler, triggerer
    core = [p for p in pods if any(
        x in p["name"] for x in ["webserver", "scheduler", "triggerer", "postgresql"]
    )]
    if len(core) < 4:
        return False

    pods_ok = all(
        p["status"] in ("Running", "Succeeded") and p["ready"] in ("true", "<none>")
        for p in pods
        if "migrations" not in p["name"] and "create-user" not in p["name"]
    )

    jobs_ok = all(
        j["condition"] == "Complete" or j["succeeded"] not in ("0", "<none>", "")
        for j in jobs
    )

    return pods_ok and jobs_ok


def _watch_airflow(namespace: str, timeout_seconds: int = 1200):
    """
    Live-updating progress display showing every pod and job status.
    Updates every 5 seconds until everything is ready or timeout.
    """
    console.print()
    start = time.time()

    with Live(console=console, refresh_per_second=0.5, transient=False) as live:
        while True:
            elapsed = int(time.time() - start)

            if elapsed > timeout_seconds:
                live.stop()
                console.print()
                console.print("[bold red]✗  Timed out waiting for Airflow.[/bold red]")
                console.print("  Check what went wrong:")
                console.print("  [yellow]kubectl get pods -n airflow[/yellow]")
                console.print("  [yellow]kubectl logs airflow-scheduler-0 -n airflow -c wait-for-airflow-migrations[/yellow]")
                sys.exit(1)

            live.update(_build_progress_table(namespace, elapsed))

            if _all_ready(namespace):
                live.stop()
                console.print()
                console.print("[bold green]  ✓  All Airflow services are ready![/bold green]")
                console.print()
                # Final summary table
                final = _build_progress_table(namespace, elapsed)
                console.print(final)
                return

            time.sleep(5)


# ── Main install function ──────────────────────────────────────────────────────

def install_airflow():
    values_file = _helm_dir() / "values" / "airflow.yaml"

    console.print()
    console.print("[bold cyan]Installing Apache Airflow...[/bold cyan]")
    console.print(f"[dim]  Values : {values_file}[/dim]")
    console.print(f"[dim]  Chart  : apache-airflow/airflow v{AIRFLOW_CHART_VERSION}[/dim]")
    console.print(f"[dim]  Image  : apache/airflow:{AIRFLOW_IMAGE_TAG}[/dim]")
    console.print()

    _sanitize_airflow_values(values_file)
    create_namespace("airflow")

    # Helm creates resources but does NOT wait — we handle progress ourselves
    cmd = [
        "helm", "upgrade", "--install", "airflow",
        "apache-airflow/airflow",
        "--version",   AIRFLOW_CHART_VERSION,
        "--namespace", "airflow",
        "--values",    str(values_file),
        "--timeout",   "5m",   # just enough for Helm to submit resources
        # No --wait, no --wait-for-jobs — we poll ourselves below
    ]

    console.print("[cyan]  Submitting resources to Kubernetes...[/cyan]")
    result = _run(cmd, check=False, capture=True)

    if result.returncode != 0:
        # Ignore "context deadline exceeded" from migration job in progress
        # Helm still created all resources even if it reports this error
        stderr = result.stderr or ""
        if "context deadline exceeded" in stderr or "InProgress" in stderr:
            console.print("[yellow]  ⚠  Helm returned timeout (resources were still created — continuing to watch)[/yellow]")
        else:
            console.print("[bold red]✗  Helm install failed.[/bold red]")
            console.print(stderr or result.stdout)
            sys.exit(1)
    else:
        console.print("[green]  ✓  Resources submitted.[/green]")

    # Now watch with live progress until everything is ready
    console.print()
    console.print("[bold]Waiting for Airflow to become ready...[/bold]")
    _watch_airflow("airflow", timeout_seconds=1200)


def uninstall_airflow():
    _run(["helm", "uninstall", "airflow", "--namespace", "airflow"], check=False)
    console.print("[green]  ✓  Airflow removed.[/green]")
