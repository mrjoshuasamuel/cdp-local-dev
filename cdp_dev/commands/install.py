import platform
import click
from rich.console import Console
from rich.rule import Rule
from rich.panel import Panel

console = Console()


@click.command()
@click.option("--skip-preflight", is_flag=True, default=False,
              help="Skip tool version checks (not recommended).")
def install(skip_preflight):
    """First-time setup: create Kind cluster and install Airflow (~5-10 min)."""
    from cdp_dev.preflight    import run_preflight
    from cdp_dev.kind_manager import create_cluster, get_kubeconfig
    from cdp_dev.helm_manager import add_repos, install_airflow
    from cdp_dev.port_forward import start_all
    from cdp_dev.path_helper  import ensure_cdpdev_globally_accessible, is_cdpdev_on_path, get_scripts_dir

    console.print()
    console.print(Panel.fit(
        "[bold cyan]CDP Local Developer Environment[/bold cyan]\n"
        "[dim]Kind + Apache Airflow[/dim]",
        border_style="cyan"
    ))
    console.print()

    # ── Step 0: Make cdp-dev available system-wide ─────────────────────────
    if platform.system() == "Windows":
        console.print(Rule("[bold]Step 0  —  System PATH[/bold]"))
        ensure_cdpdev_globally_accessible()
        if is_cdpdev_on_path():
            console.print("[green]  ✓  cdp-dev is available system-wide.[/green]")
        else:
            console.print("[dim]  cdp-dev will be available in new terminals after this run.[/dim]")

    # ── Step 1: Preflight ──────────────────────────────────────────────────
    console.print()
    console.print(Rule("[bold]Step 1 of 4  —  Preflight Checks[/bold]"))
    if not skip_preflight:
        run_preflight(verbose=True)
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

    # ── Port-forwards ──────────────────────────────────────────────────────
    console.print()
    console.print(Rule("[bold]Starting Port-Forwards[/bold]"))
    start_all()

    console.print()
    console.print(Panel(
        "[bold green]✓  Installation complete![/bold green]\n\n"
        "[bold]Airflow UI[/bold]   →  [underline cyan]http://localhost:8080[/underline cyan]\n"
        "             Username: [bold]admin[/bold]   Password: [bold]admin[/bold]\n\n"
        "[dim]Commands:[/dim]\n"
        "  cdp-dev status    — check pod health\n"
        "  cdp-dev logs      — tail Airflow logs\n"
        "  cdp-dev stop      — pause at end of day\n"
        "  cdp-dev start     — resume next morning\n"
        "  cdp-dev destroy   — delete everything",
        title="[bold cyan]CDP Local Dev[/bold cyan]",
        border_style="green",
    ))
    console.print()
