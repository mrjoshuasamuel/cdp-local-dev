import click
from rich.console import Console
from rich.rule import Rule

console = Console()


@click.command()
def stop():
    """Pause the Airflow stack (data preserved in the Postgres volume)."""
    from cdp_dev.project         import require_project_root
    from cdp_dev.compose_manager import stop as compose_stop

    console.print()
    console.print(Rule("[bold]CDP Local Dev — Stop[/bold]"))

    project_dir = require_project_root()
    console.print(f"[cyan]  Stopping containers in[/cyan] {project_dir}")
    compose_stop(project_dir)

    console.print()
    console.print("[green]  ✓  Stack paused.  Your data and DAGs are preserved.[/green]")
    console.print("    Resume with [bold cyan]cdp-dev start[/bold cyan].")
    console.print()
