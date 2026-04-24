from pathlib import Path

import click
from rich.console import Console
from rich.rule import Rule
from rich.panel import Panel

console = Console()


@click.command()
@click.option("--skip-preflight", is_flag=True, default=False,
              help="Skip Docker checks (not recommended).")
@click.option("--force", is_flag=True, default=False,
              help="Initialize a project even if CWD doesn't look like a pipeline repo.")
def install(skip_preflight, force):
    """First-time setup: initialize project dir and start the Airflow stack."""
    from cdp_dev.preflight       import run_preflight
    from cdp_dev.migration       import offer_migration
    from cdp_dev.project         import ensure_or_init
    from cdp_dev.compose_manager import up, wait_healthy

    console.print()
    console.print(Panel.fit(
        "[bold cyan]CDP Local Developer Environment[/bold cyan]\n"
        "[dim]Docker Compose + Apache Airflow[/dim]",
        border_style="cyan",
    ))
    console.print()

    # ── Step 1: Preflight ──────────────────────────────────────────────────
    console.print(Rule("[bold]Step 1 of 3  —  Preflight Checks[/bold]"))
    if skip_preflight:
        console.print("[yellow]  ⚠  Skipping preflight checks.[/yellow]")
    else:
        run_preflight(verbose=True)

    # ── Step 2: Migration + project init ───────────────────────────────────
    console.print(Rule("[bold]Step 2 of 3  —  Project Setup[/bold]"))
    offer_migration()
    project_dir = ensure_or_init(Path.cwd(), force=force)

    # ── Step 3: Start the stack ────────────────────────────────────────────
    console.print()
    console.print(Rule("[bold]Step 3 of 3  —  Starting Airflow[/bold]"))
    console.print("[cyan]  Pulling images and starting containers...[/cyan]")
    console.print("[dim]  First run downloads ~800 MB — subsequent starts are instant.[/dim]")
    up(project_dir)

    console.print()
    healthy = wait_healthy(project_dir, "airflow-webserver", timeout_s=240)
    if not healthy:
        console.print()
        console.print(Panel(
            "[bold red]✗  Airflow webserver didn't become healthy within 4 minutes.[/bold red]\n\n"
            "[dim]Diagnose with:[/dim]\n"
            f"  [yellow]cdp-dev logs webserver[/yellow]\n"
            f"  [yellow]cdp-dev status[/yellow]",
            border_style="red",
        ))
        raise SystemExit(1)

    console.print()
    console.print(Panel(
        "[bold green]✓  Airflow is up and running.[/bold green]\n\n"
        "[bold]Airflow UI[/bold]   →  [underline cyan]http://127.0.0.1:8080[/underline cyan]\n"
        "             Username: [bold]admin[/bold]   Password: [bold]admin[/bold]\n\n"
        "[bold]Your DAGs[/bold]   →  Drop Python files into [cyan]./dags/[/cyan] — picked up in ~30s.\n\n"
        "[dim]Common commands:[/dim]\n"
        "  cdp-dev test <dag_id>   — run a DAG end-to-end\n"
        "  cdp-dev logs <service>  — tail Airflow logs\n"
        "  cdp-dev status          — container health\n"
        "  cdp-dev stop            — pause\n"
        "  cdp-dev start           — resume\n"
        "  cdp-dev destroy         — delete the DB & containers",
        title="[bold cyan]CDP Local Dev[/bold cyan]",
        border_style="green",
    ))
    console.print()
