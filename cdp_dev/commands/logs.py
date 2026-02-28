import subprocess
import sys
import click
from rich.console import Console

console = Console()

SERVICE_MAP = {
    "airflow":    ("airflow",  "app.kubernetes.io/name=airflow"),
    "scheduler":  ("airflow",  "component=scheduler"),
    "webserver":  ("airflow",  "component=webserver"),
    "worker":     ("airflow",  "component=worker"),
    "triggerer":  ("airflow",  "component=triggerer"),
}


@click.command()
@click.argument("service", default="airflow",
                type=click.Choice(list(SERVICE_MAP.keys()), case_sensitive=False))
@click.option("--lines", "-n", default=50, help="Number of previous log lines to show.")
@click.option("--follow/--no-follow", "-f/ ", default=True,
              help="Follow log output (default: on).")
def logs(service, lines, follow):
    """
    Tail logs from a local CDP service.

    \b
    SERVICE options:
        airflow    — all Airflow pods
        scheduler  — Airflow scheduler only
        webserver  — Airflow webserver only
        worker     — Airflow worker pods
        triggerer  — Airflow triggerer
    """
    ns, selector = SERVICE_MAP[service.lower()]

    cmd = [
        "kubectl", "logs",
        "--selector", selector,
        "--namespace", ns,
        "--tail", str(lines),
        "--max-log-requests", "10",
        "--prefix",
    ]
    if follow:
        cmd.append("--follow")

    console.print(f"\n[cyan]  Tailing [bold]{service}[/bold] logs "
                  f"(namespace: {ns}) — Ctrl+C to stop[/cyan]\n")
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        console.print("\n[dim]  Log stream stopped.[/dim]\n")
