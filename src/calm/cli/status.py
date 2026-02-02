"""CALM status command."""

import click

from calm.config import settings


@click.command()
def status() -> None:
    """Show overall CALM system status.

    Displays:
    - Server status (running/stopped)
    - Database status
    - Configuration summary
    """
    from calm.server.daemon import get_server_pid, is_server_running

    click.echo("=== CALM System Status ===")
    click.echo()

    # Server status
    click.echo("Server:")
    if is_server_running():
        pid = get_server_pid()
        click.echo(f"  Status: Running (PID: {pid})")
        click.echo(f"  URL: http://{settings.server_host}:{settings.server_port}")
    else:
        click.echo("  Status: Stopped")
    click.echo()

    # Database status
    click.echo("Database:")
    db_path = settings.db_path
    if db_path.exists():
        size_kb = db_path.stat().st_size / 1024
        click.echo(f"  Path: {db_path}")
        click.echo(f"  Size: {size_kb:.1f} KB")

        # Get table counts
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            tables = [
                ("memories", "memories"),
                ("sessions", "session_journal"),
                ("ghap_entries", "ghap_entries"),
                ("tasks", "tasks"),
            ]

            for label, table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    click.echo(f"  {label.capitalize()}: {count}")
                except sqlite3.OperationalError:
                    pass

            conn.close()
        except Exception as e:
            click.echo(f"  Error reading database: {e}")
    else:
        click.echo("  Not initialized (run 'calm init')")
    click.echo()

    # Configuration
    click.echo("Configuration:")
    click.echo(f"  Home: {settings.home}")
    click.echo(f"  Qdrant: {settings.qdrant_url}")
