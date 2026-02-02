"""CALM backup CLI commands."""

import click

from calm.orchestration import backups as backup_ops


@click.group()
def backup() -> None:
    """Backup management commands."""
    pass


@backup.command()
@click.argument("name", required=False)
def create(name: str | None) -> None:
    """Create a named backup.

    If NAME is not provided, a timestamp-based name is generated.
    """
    try:
        result = backup_ops.create_backup(name)
        size_kb = result.size_bytes / 1024
        click.echo(f"Created backup: {result.name}")
        click.echo(f"Path: {result.path}")
        click.echo(f"Size: {size_kb:.1f} KB")
    except FileNotFoundError as e:
        raise click.ClickException(str(e))


@backup.command("list")
def list_cmd() -> None:
    """List available backups."""
    backups = backup_ops.list_backups()

    if not backups:
        click.echo("No backups found.")
        return

    click.echo(f"{'Name':<30} {'Size':<10} {'Created'}")
    click.echo("-" * 60)

    for b in backups:
        size_kb = b.size_bytes / 1024
        created = b.created_at.strftime("%Y-%m-%d %H:%M:%S")
        click.echo(f"{b.name:<30} {size_kb:>7.1f} KB {created}")


@backup.command()
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to restore this backup?")
def restore(name: str) -> None:
    """Restore from a backup."""
    try:
        backup_ops.restore_backup(name)
        click.echo(f"Restored from backup: {name}")
    except FileNotFoundError as e:
        raise click.ClickException(str(e))


@backup.command()
@click.option("--max-backups", default=10, help="Maximum auto-backups to keep")
def auto(max_backups: int) -> None:
    """Create an auto-backup and rotate old ones."""
    try:
        result = backup_ops.auto_backup(max_backups=max_backups)
        click.echo(f"Created auto-backup: {result.name}")
    except FileNotFoundError as e:
        raise click.ClickException(str(e))


@backup.command()
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to delete this backup?")
def delete(name: str) -> None:
    """Delete a backup."""
    try:
        backup_ops.delete_backup(name)
        click.echo(f"Deleted backup: {name}")
    except FileNotFoundError as e:
        raise click.ClickException(str(e))
