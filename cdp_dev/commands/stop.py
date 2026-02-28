import click
from rich.console import Console
from rich.rule import Rule

console = Console()


@click.command()
def stop():
    """Pause the Kind cluster (data is preserved). Resume with cdp-dev start."""
    from cdp_dev.kind_manager import stop_cluster
    from cdp_dev.port_forward import stop_all

    console.print()
    console.print(Rule("[bold]CDP Local Dev — Stop[/bold]"))

    console.print("[cyan]  Stopping port-forwards...[/cyan]")
    stop_all()

    stop_cluster()

    console.print()
    console.print("[bold green]✓  Environment paused. Run [bold]cdp-dev start[/bold] to resume.[/bold green]")
    console.print()
