import subprocess
import click
from rich.console import Console
from rich.table import Table
from rich.rule import Rule
from rich import box

console = Console()


def _kubectl(args: list) -> str:
    try:
        return subprocess.check_output(
            ["kubectl"] + args, stderr=subprocess.DEVNULL, text=True
        )
    except Exception:
        return ""


@click.command()
def status():
    """Show the health of all local CDP pods and port-forwards."""
    from cdp_dev.kind_manager import cluster_exists, cluster_running
    from cdp_dev.port_forward import status as pf_status

    console.print()
    console.print(Rule("[bold]CDP Local Dev — Status[/bold]"))
    console.print()

    # ── Cluster status ─────────────────────────────────────────────────────
    exists  = cluster_exists()
    running = cluster_running()

    if not exists:
        console.print("[red]  ✗  Cluster 'cdp-local' does not exist.[/red]")
        console.print("     Run [bold cyan]cdp-dev install[/bold cyan] to set it up.")
        return

    cluster_state = "[green]Running[/green]" if running else "[yellow]Stopped[/yellow]"
    console.print(f"  Kind cluster [bold]cdp-local[/bold]:  {cluster_state}")
    console.print()

    if not running:
        console.print("  Run [bold cyan]cdp-dev start[/bold cyan] to resume the cluster.")
        return

    # ── Pod status ─────────────────────────────────────────────────────────
    raw = _kubectl(["get", "pods", "--all-namespaces",
                    "-o", "custom-columns=NS:.metadata.namespace,NAME:.metadata.name,"
                           "STATUS:.status.phase,READY:.status.containerStatuses[0].ready"])

    pod_table = Table(title="Pods", box=box.ROUNDED, show_lines=True)
    pod_table.add_column("Namespace", style="cyan",   no_wrap=True)
    pod_table.add_column("Pod",       style="white",  no_wrap=True)
    pod_table.add_column("Status",    justify="center")
    pod_table.add_column("Ready",     justify="center")

    lines = [l for l in raw.splitlines() if l.strip() and "NS" not in l]
    if not lines:
        console.print("[yellow]  No pods found. The cluster may still be starting.[/yellow]")
    else:
        for line in lines:
            parts = line.split()
            if len(parts) < 3:
                continue
            ns, name = parts[0], parts[1]
            phase    = parts[2] if len(parts) > 2 else "—"
            ready    = parts[3] if len(parts) > 3 else "—"

            phase_fmt = (
                "[green]Running[/green]"   if phase == "Running"   else
                "[cyan]Pending[/cyan]"     if phase == "Pending"   else
                "[yellow]Unknown[/yellow]" if phase == "<none>"    else
                f"[red]{phase}[/red]"
            )
            ready_fmt = (
                "[green]✓[/green]" if ready == "true"  else
                "[red]✗[/red]"     if ready == "false" else
                "[dim]—[/dim]"
            )
            pod_table.add_row(ns, name, phase_fmt, ready_fmt)

        console.print(pod_table)

    # ── Port-forward status ────────────────────────────────────────────────
    console.print()
    pf_table = Table(title="Port Forwards", box=box.ROUNDED, show_lines=True)
    pf_table.add_column("Service",    style="cyan")
    pf_table.add_column("URL",        style="underline")
    pf_table.add_column("Status",     justify="center")

    for fwd in pf_status():
        state = "[green]✓  Active[/green]" if fwd["alive"] else "[red]✗  Down[/red]"
        pf_table.add_row(fwd["name"], fwd["url"], state)

    console.print(pf_table)
    console.print()

    # ── Quick tips ─────────────────────────────────────────────────────────
    console.print("  [dim]cdp-dev logs   → tail Airflow logs[/dim]")
    console.print("  [dim]cdp-dev stop   → pause cluster[/dim]")
    console.print()
