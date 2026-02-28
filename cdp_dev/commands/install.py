"""
cdp-dev install

Full first-time setup:
  1. Preflight checks
  2. Create Kind cluster
  3. Add Helm repos
  4. Install Airflow
  5. Start port-forwards
  6. Print access URLs
"""
import click
from rich.console import Console
from rich.rule import Rule
from rich.panel import Panel

console = Console()


@click.command()
@click.option("--skip-preflight", is_flag=True, default=False,
              help="Skip tool version checks (not recommended).")
def install(skip_preflight):
    """
    First-time setup: create Kind cluster and install Airflow.

    Run this once after installing cdp-dev. Takes ~5 minutes.
    """
    from cdp_dev.preflight    import run_preflight
    from cdp_dev.kind_manager import create_cluster, get_kubeconfig
    from cdp_dev.helm_manager import add_repos, install_airflow
    from cdp_dev.port_forward import start_all

    console.print()
    console.print(Panel.fit(
        "[bold cyan]CDP Local Developer Environment[/bold cyan]\n"
        "[dim]Kind + Apache Airflow[/dim]",
        border_style="cyan"
    ))
    console.print()

    # ── Step 1: Preflight ──────────────────────────────────────────────────
    console.print(Rule("[bold]Step 1 of 4  —  Preflight Checks[/bold]"))
    if not skip_preflight:
        ok = run_preflight(verbose=True)
        if not ok:
            raise click.Abort()
    else:
        console.print("[yellow]  ⚠  Skipping preflight checks.[/yellow]")

    # ── Step 2: Kind Cluster ───────────────────────────────────────────────
    console.print()
    console.print(Rule("[bold]Step 2 of 4  —  Kind Cluster[/bold]"))
    create_cluster()
    get_kubeconfig()

    # ── Step 3: Helm Repos ─────────────────────────────────────────────────
    console.print()
    console.print(Rule("[bold]Step 3 of 4  —  Helm Repositories[/bold]"))
    add_repos()

    # ── Step 4: Airflow ────────────────────────────────────────────────────
    console.print()
    console.print(Rule("[bold]Step 4 of 4  —  Apache Airflow[/bold]"))
    install_airflow()

    # ── Port-forwards & summary ────────────────────────────────────────────
    console.print()
    console.print(Rule("[bold]Starting Port-Forwards[/bold]"))
    start_all()

    console.print()
    console.print(Panel(
        "[bold green]✓  Installation complete![/bold green]\n\n"
        "[bold]Airflow UI[/bold]   →  [underline cyan]http://localhost:8080[/underline cyan]\n"
        "             Username: [bold]admin[/bold]   Password: [bold]admin[/bold]\n\n"
        "[dim]Useful commands:[/dim]\n"
        "  cdp-dev status    — check pod health\n"
        "  cdp-dev logs      — tail Airflow logs\n"
        "  cdp-dev stop      — pause cluster at end of day\n"
        "  cdp-dev start     — resume next morning\n"
        "  cdp-dev destroy   — delete everything",
        title="[bold cyan]CDP Local Dev[/bold cyan]",
        border_style="green",
    ))
    console.print()
