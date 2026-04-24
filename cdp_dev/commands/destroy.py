import click
from rich.console import Console
from rich.rule import Rule

console = Console()


@click.command()
@click.confirmation_option(
    prompt="This will delete containers and the Postgres volume (metadata DB). Your ./dags and ./logs are kept. Continue?"
)
def destroy():
    """
    Delete containers and the Airflow metadata volume.

    Your local ./dags, ./logs, and ./plugins directories are NOT touched —
    only Docker containers and the Postgres named volume are removed.
    Run cdp-dev install to start fresh.
    """
    from cdp_dev.project         import require_project_root
    from cdp_dev.compose_manager import down

    console.print()
    console.print(Rule("[bold red]CDP Local Dev — Destroy[/bold red]"))

    project_dir = require_project_root()
    console.print(f"[cyan]  Removing containers + volumes in[/cyan] {project_dir}")
    down(project_dir, volumes=True)

    console.print()
    console.print("[bold green]✓  Containers and metadata DB removed.[/bold green]")
    console.print("   Your DAGs and logs are preserved in this directory.")
    console.print("   Run [bold cyan]cdp-dev install[/bold cyan] to rebuild.")
    console.print()
