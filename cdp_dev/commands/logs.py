import click
from rich.console import Console

console = Console()

SERVICES = {
    "airflow":    None,   # None = all services
    "webserver":  "airflow-webserver",
    "scheduler":  "airflow-scheduler",
    "triggerer":  "airflow-triggerer",
    "postgres":   "postgres",
}


@click.command()
@click.argument("service", default="airflow",
                type=click.Choice(list(SERVICES.keys()), case_sensitive=False))
@click.option("--lines", "-n", default=50, help="Number of previous log lines to show.")
@click.option("--follow/--no-follow", "-f/ ", default=True,
              help="Follow log output (default: on).")
def logs(service, lines, follow):
    """
    Tail logs from Airflow services.

    \b
    SERVICE options:
        airflow    — all services (default)
        webserver  — Airflow webserver
        scheduler  — Airflow scheduler
        triggerer  — Airflow triggerer
        postgres   — metadata database
    """
    from cdp_dev.project         import require_project_root
    from cdp_dev.compose_manager import logs as compose_logs

    project_dir   = require_project_root()
    service_name  = SERVICES[service.lower()]

    target = service_name or "all services"
    console.print(f"\n[cyan]  Tailing logs for [bold]{target}[/bold] "
                  f"(Ctrl+C to stop)[/cyan]\n")
    try:
        compose_logs(project_dir, service=service_name, follow=follow, tail=lines)
    except KeyboardInterrupt:
        console.print("\n[dim]  Log stream stopped.[/dim]\n")
