from datetime import date

import click
from rich.console import Console

console = Console()


@click.command()
@click.argument("dag_id")
@click.option(
    "--date", "exec_date",
    default=None,
    help="Execution date as YYYY-MM-DD (defaults to today).",
)
def test(dag_id: str, exec_date: str | None):
    """
    Run a DAG end-to-end via `airflow dags test`.

    This executes the full DAG in-process inside the scheduler container
    without involving the scheduler loop — the fastest feedback loop for
    iterating on DAG code.
    """
    from cdp_dev.project         import require_project_root
    from cdp_dev.compose_manager import exec_in

    project_dir = require_project_root()
    run_date    = exec_date or date.today().isoformat()

    console.print()
    console.print(
        f"[cyan]  Running DAG [bold]{dag_id}[/bold] for execution date "
        f"[bold]{run_date}[/bold]...[/cyan]"
    )
    console.print()

    result = exec_in(
        project_dir,
        service="airflow-scheduler",
        cmd=["airflow", "dags", "test", dag_id, run_date],
    )
    raise SystemExit(result.returncode)
