"""
migration.py — one-shot migration from the old Kind+Helm layout.

Runs on `cdp-dev install` and is a no-op whenever the `kind` binary isn't on
PATH (post-migration users).  If a cluster named `cdp-local` exists, offer
to delete it before proceeding with the Compose-based install.
"""
from __future__ import annotations

import shutil
import subprocess

import click
from rich.console import Console

console = Console()

OLD_CLUSTER_NAME = "cdp-local"


def _kind_available() -> bool:
    return shutil.which("kind") is not None


def detect_old_kind_cluster() -> bool:
    if not _kind_available():
        return False
    try:
        result = subprocess.run(
            ["kind", "get", "clusters"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return OLD_CLUSTER_NAME in result.stdout.splitlines()


def offer_migration() -> None:
    if not detect_old_kind_cluster():
        return

    console.print()
    console.print(
        "[yellow]  ⚠  Found an old Kind cluster "
        f"[bold]{OLD_CLUSTER_NAME}[/bold] from the previous Helm-based setup.[/yellow]"
    )
    console.print(
        "[dim]     cdp-local-dev now uses Docker Compose — the Kind cluster is no longer needed.[/dim]"
    )

    if click.confirm(
        f"  Delete the old Kind cluster '{OLD_CLUSTER_NAME}'?", default=True
    ):
        console.print(f"[cyan]  Deleting Kind cluster '{OLD_CLUSTER_NAME}'...[/cyan]")
        subprocess.run(
            ["kind", "delete", "cluster", "--name", OLD_CLUSTER_NAME],
            check=False,
        )
        console.print("[green]  ✓  Old cluster removed.[/green]")
    else:
        console.print(
            "[dim]  Skipped.  You can delete it later with: "
            f"[cyan]kind delete cluster --name {OLD_CLUSTER_NAME}[/cyan][/dim]"
        )
