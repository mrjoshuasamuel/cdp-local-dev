"""
port_forward.py
Starts kubectl port-forward processes in the background so developers
can access Airflow at http://localhost:8080 without any manual steps.

Port-forwards die when the terminal closes, so we track PIDs in a state
file (~/.cdp-dev/port-forwards.json) and restart them on cdp-dev start.
"""
import json
import os
import subprocess
import time
from pathlib import Path

from rich.console import Console

console = Console()

STATE_DIR  = Path.home() / ".cdp-dev"
STATE_FILE = STATE_DIR / "port-forwards.json"

FORWARDS = [
    {
        "name":       "Airflow UI",
        "namespace":  "airflow",
        "service":    "svc/airflow-webserver",
        "local_port": 8080,
        "remote_port": 8080,
        "url":        "http://localhost:8080",
    },
]


def _state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_state(data: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2))


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def start_all():
    """Start all port-forwards in the background."""
    state = _state()
    for fwd in FORWARDS:
        name = fwd["name"]
        existing_pid = state.get(name)
        if existing_pid and _pid_alive(existing_pid):
            console.print(f"[yellow]  ⚠  Port-forward '{name}' already running (PID {existing_pid}).[/yellow]")
            continue

        proc = subprocess.Popen(
            [
                "kubectl", "port-forward",
                fwd["service"],
                f"{fwd['local_port']}:{fwd['remote_port']}",
                "-n", fwd["namespace"],
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)  # give it a moment to bind
        state[name] = proc.pid
        console.print(
            f"[green]  ✓  {name}[/green] → "
            f"[bold underline cyan]{fwd['url']}[/bold underline cyan]"
            f"  [dim](PID {proc.pid})[/dim]"
        )

    _save_state(state)


def stop_all():
    """Kill all tracked port-forward processes."""
    state = _state()
    for name, pid in state.items():
        if _pid_alive(pid):
            try:
                os.kill(pid, 15)  # SIGTERM
                console.print(f"[green]  ✓  Stopped port-forward '{name}' (PID {pid}).[/green]")
            except Exception as e:
                console.print(f"[yellow]  Could not stop '{name}': {e}[/yellow]")
    _save_state({})


def status() -> list:
    """Return list of dicts with current port-forward status."""
    state   = _state()
    results = []
    for fwd in FORWARDS:
        pid   = state.get(fwd["name"])
        alive = pid is not None and _pid_alive(pid)
        results.append({
            "name":       fwd["name"],
            "url":        fwd["url"],
            "local_port": fwd["local_port"],
            "pid":        pid,
            "alive":      alive,
        })
    return results
