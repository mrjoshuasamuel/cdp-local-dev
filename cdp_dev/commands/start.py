import click
from rich.console import Console
from rich.rule import Rule

console = Console()


@click.command()
def start():
    """Resume the Airflow stack after `cdp-dev stop` or a reboot."""
    from cdp_dev.project         import require_project_root
    from cdp_dev.compose_manager import start as compose_start, wait_healthy

    console.print()
    console.print(Rule("[bold]CDP Local Dev — Start[/bold]"))

    project_dir = require_project_root()
    console.print(f"[cyan]  Starting containers in[/cyan] {project_dir}")
    compose_start(project_dir)

    console.print()
    wait_healthy(project_dir, "airflow-webserver", timeout_s=180)

    console.print()
    console.print("[bold green]✓  Environment is running.[/bold green]")
    console.print("   Airflow UI → [underline cyan]http://127.0.0.1:8080[/underline cyan]  (admin / admin)")
    console.print()
