"""
project.py — locate and initialize a cdp-local-dev project directory.

A project dir is any directory containing `.cdp-dev/state.json`.
Non-install commands use find_project_root() (walks up from CWD, git-style).
`cdp-dev install` creates a new project in CWD, prompting first if CWD
doesn't look like a real project (missing dags/ and .git).
"""
from __future__ import annotations

import base64
import json
import os
import platform
import secrets
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console

from .compose_manager import template_path
from .utils import IS_LINUX

console = Console()

PROJECT_MARKER = ".cdp-dev"
STATE_FILE = "state.json"


# ── Discovery ────────────────────────────────────────────────────────────────

def find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from `start` (default CWD) looking for a .cdp-dev/ marker."""
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / PROJECT_MARKER / STATE_FILE).exists():
            return candidate
    return None


def require_project_root() -> Path:
    """Return the project root or exit with a helpful message."""
    root = find_project_root()
    if root is None:
        console.print(
            "[red]  ✗  No cdp-local-dev project found in this directory or any parent.[/red]"
        )
        console.print("     Run [bold cyan]cdp-dev install[/bold cyan] from your pipeline repo first.")
        sys.exit(1)
    return root


# ── Initialization ───────────────────────────────────────────────────────────

def _looks_like_pipeline_dir(path: Path) -> bool:
    return (path / "dags").is_dir() or (path / ".git").exists()


def _generate_fernet_key() -> str:
    # Fernet keys are 32 random bytes, url-safe base64 encoded.
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


def _generate_secret_key() -> str:
    return secrets.token_urlsafe(32)


def _resolve_airflow_uid() -> int:
    # Linux: run as the invoking user so bind-mounted logs/dags stay writable.
    # macOS / Windows: Docker Desktop handles UID mapping; the Airflow default is fine.
    if IS_LINUX and hasattr(os, "getuid"):
        return os.getuid()
    return 50000


def ensure_or_init(project_dir: Path, force: bool = False) -> Path:
    """
    Ensure `project_dir` is a cdp-local-dev project.  Create one if missing,
    prompting first when the directory doesn't look like a pipeline repo.

    Returns the resolved project dir (absolute).
    """
    project_dir = project_dir.resolve()
    marker = project_dir / PROJECT_MARKER

    # Already initialized?
    if (marker / STATE_FILE).exists():
        _ensure_env_file(project_dir)
        _ensure_compose_file(project_dir)
        _ensure_dag_dirs(project_dir)
        return project_dir

    # First-time init — guard against accidental clutter in $HOME or /tmp.
    if not force and not _looks_like_pipeline_dir(project_dir):
        console.print(
            f"[yellow]  ⚠  No [bold]dags/[/bold] or [bold].git[/bold] found in "
            f"{project_dir}.[/yellow]"
        )
        if not click.confirm(
            "  Initialize a new cdp-local-dev project here?", default=False
        ):
            console.print(
                "[dim]  Aborted.  cd into your pipeline repo and re-run "
                "[cyan]cdp-dev install[/cyan].[/dim]"
            )
            sys.exit(0)

    console.print(f"[cyan]  Initializing project in[/cyan] {project_dir}")
    marker.mkdir(parents=True, exist_ok=True)
    _ensure_dag_dirs(project_dir)
    _ensure_compose_file(project_dir)
    _ensure_env_file(project_dir)

    state = {
        "version":    "0.2.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "platform":   platform.platform(),
    }
    (marker / STATE_FILE).write_text(json.dumps(state, indent=2))
    console.print(f"[green]  ✓  Project initialized.[/green]")
    return project_dir


def _ensure_dag_dirs(project_dir: Path) -> None:
    for sub in ("dags", "logs", "plugins"):
        (project_dir / sub).mkdir(exist_ok=True)


def _ensure_compose_file(project_dir: Path) -> None:
    target = project_dir / "docker-compose.yml"
    source = template_path("docker-compose.yml")
    # Overwrite on every install so users get fixes to the template.  Warn if
    # they've hand-edited (header marker missing).
    if target.exists() and "cdp-local-dev managed" not in target.read_text():
        console.print(
            f"[yellow]  ⚠  Existing {target.name} was hand-edited — leaving it in place.[/yellow]"
        )
        return
    shutil.copyfile(source, target)


def _ensure_env_file(project_dir: Path) -> None:
    target = project_dir / ".env"
    if target.exists():
        return   # keep existing keys across reinstalls
    tmpl = template_path(".env.template").read_text()
    rendered = (
        tmpl.replace("__AIRFLOW_UID__",                 str(_resolve_airflow_uid()))
            .replace("__AIRFLOW_FERNET_KEY__",          _generate_fernet_key())
            .replace("__AIRFLOW_WEBSERVER_SECRET_KEY__", _generate_secret_key())
    )
    target.write_text(rendered)
