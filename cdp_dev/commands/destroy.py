import click
from rich.console import Console
from rich.rule import Rule

console = Console()


@click.command()
@click.confirmation_option(
    prompt="[red]This will delete the Kind cluster and ALL local data. Are you sure?[/red]"
)
def destroy():
    """
    Delete the Kind cluster and all local state.

    WARNING: This is irreversible. All Airflow data, DAGs, and logs
    stored in the local cluster will be permanently deleted.
    Run cdp-dev install to start fresh.
    """
    from cdp_dev.port_forward import stop_all
    from cdp_dev.kind_manager import delete_cluster

    console.print()
    console.print(Rule("[bold red]CDP Local Dev — Destroy[/bold red]"))

    console.print("[cyan]  Stopping port-forwards...[/cyan]")
    stop_all()

    console.print("[cyan]  Deleting Kind cluster...[/cyan]")
    delete_cluster()

    console.print()
    console.print("[bold green]✓  Everything removed.[/bold green]")
    console.print("   Run [bold cyan]cdp-dev install[/bold cyan] to start fresh.")
    console.print()
