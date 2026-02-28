import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="cdp-dev")
def main():
    """
    CDP Local Developer Environment

    Spin up a local Kubernetes (Kind) cluster with Apache Airflow
    so you can develop and test pipelines without touching the cloud.

    \b
    Quick start:
        cdp-dev install     # first time setup (~5 min)
        cdp-dev status      # check everything is healthy
        cdp-dev stop        # pause at end of day
        cdp-dev start       # resume next morning
    """
    # Silently ensure pip Scripts dir is on PATH on Windows
    # so cdp-dev works from any terminal without manual PATH edits
    from cdp_dev.path_helper import ensure_on_path
    ensure_on_path()


from cdp_dev.commands.install import install
from cdp_dev.commands.start   import start
from cdp_dev.commands.stop    import stop
from cdp_dev.commands.status  import status
from cdp_dev.commands.logs    import logs
from cdp_dev.commands.destroy import destroy

main.add_command(install)
main.add_command(start)
main.add_command(stop)
main.add_command(status)
main.add_command(logs)
main.add_command(destroy)
