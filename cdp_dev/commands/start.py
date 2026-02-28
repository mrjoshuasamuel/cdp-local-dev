import click
from rich.console import Console
from rich.rule import Rule

console = Console()


@click.command()
def start():
    """Resume the Kind cluster and port-forwards after a reboot or cdp-dev stop."""
    from cdp_dev.kind_manager import start_cluster, get_kubeconfig
    from cdp_dev.port_forward import start_all

    console.print()
    console.print(Rule("[bold]CDP Local Dev — Start[/bold]"))

    start_cluster()
    get_kubeconfig()

    console.print()
    console.print("[cyan]  Starting port-forwards...[/cyan]")
    start_all()

    console.print()
    console.print("[bold green]✓  Environment is running.[/bold green]")
    console.print("   Airflow UI → [underline cyan]http://localhost:8080[/underline cyan]  (admin / admin)")
    console.print()
