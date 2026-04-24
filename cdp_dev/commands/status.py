import click
from rich.console import Console
from rich.table import Table
from rich.rule import Rule
from rich import box

console = Console()


@click.command()
def status():
    """Show health of all containers in the Airflow stack."""
    from cdp_dev.project         import require_project_root
    from cdp_dev.compose_manager import ps, service_health

    project_dir = require_project_root()

    console.print()
    console.print(Rule("[bold]CDP Local Dev — Status[/bold]"))
    console.print(f"[dim]  Project: {project_dir}[/dim]")
    console.print()

    rows = ps(project_dir)
    if not rows:
        console.print("[yellow]  No containers found.[/yellow]")
        console.print("     Run [bold cyan]cdp-dev start[/bold cyan] or [bold cyan]cdp-dev install[/bold cyan].")
        console.print()
        return

    table = Table(title="Services", box=box.ROUNDED, show_lines=True)
    table.add_column("Service", style="cyan",  no_wrap=True)
    table.add_column("State",   justify="center")
    table.add_column("Health",  justify="center")
    table.add_column("Ports",   style="dim")

    for row in rows:
        name  = row.get("Service") or row.get("Name") or "?"
        state = row.get("State",  "unknown")
        ports = row.get("Publishers") or row.get("Ports") or ""
        if isinstance(ports, list):
            ports = ", ".join(
                f"{p.get('PublishedPort','')}:{p.get('TargetPort','')}"
                for p in ports if p.get("PublishedPort")
            )

        health = row.get("Health") or service_health(project_dir, name)
        health_fmt = {
            "healthy":   "[green]✓  healthy[/green]",
            "starting":  "[yellow]⏳ starting[/yellow]",
            "unhealthy": "[red]✗  unhealthy[/red]",
        }.get(health, f"[dim]{health or '—'}[/dim]")

        state_fmt = (
            "[green]running[/green]" if state == "running"
            else f"[yellow]{state}[/yellow]" if state in ("exited", "restarting", "paused")
            else f"[red]{state}[/red]"
        )
        table.add_row(name, state_fmt, health_fmt, str(ports))

    console.print(table)
    console.print()
    console.print("  [dim]cdp-dev logs <service>  → tail logs[/dim]")
    console.print("  [dim]cdp-dev test <dag_id>   → run a DAG[/dim]")
    console.print()
