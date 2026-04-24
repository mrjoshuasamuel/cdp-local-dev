"""
compose_manager.py — thin wrapper around `docker compose`.

All commands pass --project-directory and -f explicitly so CWD-relative
confusion cannot bite us.  The compose CLI binary is resolved once at import
time (preflight sets COMPOSE_CMD to either ["docker", "compose"] or legacy
["docker-compose"]).
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Iterable

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


# Default compose command — preflight may override via set_compose_cmd().
COMPOSE_CMD: list[str] = ["docker", "compose"]


def set_compose_cmd(cmd: list[str]) -> None:
    global COMPOSE_CMD
    COMPOSE_CMD = cmd


# ── Template resolution (mirrors _helm_dir() pattern from the old codebase) ──

def template_path(name: str) -> Path:
    """Locate a shipped template, whether installed via pip or editable."""
    pkg = Path(__file__).parent / "templates" / name
    if pkg.exists():
        return pkg
    raise FileNotFoundError(
        f"Template {name!r} not found at {pkg}. Reinstall cdp-local-dev."
    )


# ── Core command runner ──────────────────────────────────────────────────────

def compose(
    args: Iterable[str],
    project_dir: Path,
    capture: bool = False,
    check: bool = True,
    stream: bool = False,
) -> subprocess.CompletedProcess:
    """
    Run `docker compose <args...>` against the given project.

    stream=True  → inherit stdio (for `logs -f`, `exec`).
    capture=True → capture stdout/stderr for programmatic parsing.
    """
    compose_file = project_dir / "docker-compose.yml"
    cmd = [
        *COMPOSE_CMD,
        "--project-directory", str(project_dir),
        "-f", str(compose_file),
        *args,
    ]
    if stream:
        return subprocess.run(cmd, check=check)
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)


# ── Public API ───────────────────────────────────────────────────────────────

def up(project_dir: Path) -> None:
    compose(["up", "-d"], project_dir)


def down(project_dir: Path, volumes: bool = False) -> None:
    args = ["down"]
    if volumes:
        args.append("-v")
    compose(args, project_dir, check=False)


def start(project_dir: Path) -> None:
    compose(["start"], project_dir)


def stop(project_dir: Path) -> None:
    compose(["stop"], project_dir, check=False)


def ps(project_dir: Path) -> list[dict]:
    """Return a list of service dicts as reported by `compose ps --format json`."""
    result = compose(
        ["ps", "--all", "--format", "json"],
        project_dir, capture=True, check=False,
    )
    rows: list[dict] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            rows.extend(parsed)
        else:
            rows.append(parsed)
    return rows


def logs(
    project_dir: Path,
    service: str | None = None,
    follow: bool = True,
    tail: int = 50,
) -> None:
    args = ["logs", f"--tail={tail}"]
    if follow:
        args.append("-f")
    if service:
        args.append(service)
    compose(args, project_dir, stream=True, check=False)


def exec_in(
    project_dir: Path,
    service: str,
    cmd: list[str],
    tty: bool = False,
) -> subprocess.CompletedProcess:
    args = ["exec"]
    if not tty:
        args.append("-T")
    args.append(service)
    args.extend(cmd)
    return compose(args, project_dir, stream=True, check=False)


# ── Health polling ───────────────────────────────────────────────────────────

def service_health(project_dir: Path, service: str) -> str:
    """
    Return "healthy", "unhealthy", "starting", or "unknown" for a compose service.
    Reads docker inspect on the first matching container.
    """
    result = compose(
        ["ps", "-q", service],
        project_dir, capture=True, check=False,
    )
    cid = result.stdout.strip().splitlines()
    if not cid:
        return "unknown"
    inspect = subprocess.run(
        ["docker", "inspect", "--format",
         "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}",
         cid[0]],
        capture_output=True, text=True, check=False,
    )
    return inspect.stdout.strip() or "unknown"


def wait_healthy(
    project_dir: Path,
    service: str,
    timeout_s: int = 180,
) -> bool:
    """
    Block until `service` reports healthy, or timeout.
    Returns True on success, False on timeout.  Renders a Rich spinner.
    """
    start = time.time()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task(
            f"Waiting for {service} to become healthy...", total=None
        )
        while time.time() - start < timeout_s:
            status = service_health(project_dir, service)
            elapsed = int(time.time() - start)
            progress.update(
                task,
                description=f"Waiting for {service} — {status} ({elapsed}s)",
            )
            if status == "healthy":
                return True
            if status == "unhealthy":
                # Let it keep trying until timeout — healthcheck may have flaked.
                pass
            time.sleep(3)
    return False
