"""
cli.py — CDP Local Dev main entry point.

Can be invoked two ways:
  1. cdp-dev install       (after PATH is fixed)
  2. python -m cdp_dev install  (always works, python is always on PATH)

On first run, automatically installs cdp-dev.bat into System32
so `cdp-dev` works in every terminal from that point on.
"""
import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="cdp-dev")
def main():
    """
    CDP Local Developer Environment

    Run Apache Airflow locally in Docker Compose so you can develop
    and test DAGs on your laptop without touching the cloud.

    \b
    Quick start — from inside your pipeline repo:
        cdp-dev install          # init project + start Airflow
        # write DAGs under ./dags — scheduler picks them up in ~30s
        cdp-dev test <dag_id>    # run a DAG end-to-end
        cdp-dev stop             # pause at end of day
        cdp-dev start            # resume next morning
    """
    # On every invocation, silently ensure cdp-dev.bat is in System32
    # so the short `cdp-dev` command works in all future terminals
    from cdp_dev.path_helper import ensure_cdpdev_globally_accessible
    ensure_cdpdev_globally_accessible()


from cdp_dev.commands.install import install
from cdp_dev.commands.start   import start
from cdp_dev.commands.stop    import stop
from cdp_dev.commands.status  import status
from cdp_dev.commands.logs    import logs
from cdp_dev.commands.destroy import destroy
from cdp_dev.commands.test    import test

main.add_command(install)
main.add_command(start)
main.add_command(stop)
main.add_command(status)
main.add_command(logs)
main.add_command(destroy)
main.add_command(test)
