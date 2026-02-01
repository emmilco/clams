"""CALM server management commands."""

import click

from calm.config import settings


@click.group()
def server() -> None:
    """Manage the CALM server daemon."""
    pass


@server.command("start")
@click.option(
    "--foreground", "-f", is_flag=True, help="Run in foreground (don't daemonize)"
)
def start(foreground: bool) -> None:
    """Start the CALM server daemon.

    By default, starts as a background daemon. Use --foreground to run
    in the foreground (useful for debugging).
    """
    from calm.server.daemon import is_server_running, run_foreground, start_daemon

    if is_server_running():
        click.echo("Server is already running")
        return

    host, port = settings.server_host, settings.server_port
    if foreground:
        click.echo(f"Starting CALM server on {host}:{port}...")
        run_foreground()
    else:
        click.echo(f"Starting CALM server daemon on {host}:{port}...")
        start_daemon()


@server.command("stop")
def stop() -> None:
    """Stop the running CALM server daemon."""
    from calm.server.daemon import stop_server

    if stop_server():
        click.echo("Server stopped")
    else:
        click.echo("Server was not running")


@server.command("status")
def status() -> None:
    """Show CALM server status."""
    from calm.server.daemon import get_server_pid, is_server_running

    if is_server_running():
        pid = get_server_pid()
        click.echo(f"Server is running (PID: {pid})")
        click.echo(f"  Host: {settings.server_host}")
        click.echo(f"  Port: {settings.server_port}")
        click.echo(f"  PID file: {settings.pid_file}")
        click.echo(f"  Log file: {settings.log_file}")
    else:
        click.echo("Server is not running")


@server.command("restart")
def restart() -> None:
    """Restart the CALM server daemon."""
    from calm.server.daemon import is_server_running, start_daemon, stop_server

    if is_server_running():
        click.echo("Stopping server...")
        stop_server()

    host, port = settings.server_host, settings.server_port
    click.echo(f"Starting CALM server daemon on {host}:{port}...")
    start_daemon()
