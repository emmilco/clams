"""CALM backup CLI commands."""

import click

from calm.config import settings
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
    Backs up both the SQLite metadata database and Qdrant vector store.
    If Qdrant is unreachable, only the SQLite database is backed up.
    """
    try:
        result = backup_ops.create_backup(name)
        size_kb = result.size_bytes / 1024
        click.echo(f"Created backup: {result.name}")
        click.echo(f"Path: {result.path}")
        click.echo(f"Size: {size_kb:.1f} KB")
        if result.has_qdrant_snapshot:
            qdrant_size_bytes = sum(
                f.stat().st_size
                for f in result.qdrant_snapshot_path.glob("*.snapshot")
            ) if result.qdrant_snapshot_path else 0
            qdrant_size_kb = qdrant_size_bytes / 1024
            click.echo(
                f"Qdrant snapshot: {result.qdrant_snapshot_path} "
                f"({qdrant_size_kb:.1f} KB)"
            )
        else:
            click.echo("Qdrant snapshot: not included (Qdrant unreachable)")
    except FileNotFoundError as e:
        raise click.ClickException(str(e))


@backup.command("list")
def list_cmd() -> None:
    """List available backups."""
    backups = backup_ops.list_backups()
    max_backups = settings.max_backups

    if not backups:
        click.echo(f"No backups found. (max: {max_backups})")
        return

    click.echo(f"{len(backups)} of {max_backups} backups (max: {max_backups})")
    click.echo()
    click.echo(f"{'Name':<30} {'Size':<10} {'Qdrant':<8} {'Created'}")
    click.echo("-" * 70)

    for b in backups:
        size_kb = b.size_bytes / 1024
        created = b.created_at.strftime("%Y-%m-%d %H:%M:%S")
        qdrant_status = "Yes" if b.has_qdrant_snapshot else "No"
        click.echo(
            f"{b.name:<30} {size_kb:>7.1f} KB {qdrant_status:<8} {created}"
        )


@backup.command()
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to restore this backup?")
def restore(name: str) -> None:
    """Restore from a backup.

    Restores the SQLite database and, if available, the Qdrant vector store.
    """
    try:
        qdrant_restored = backup_ops.restore_backup(name)
        click.echo(f"Restored from backup: {name}")
        if qdrant_restored:
            click.echo("Qdrant vector store: restored")
        else:
            click.echo(
                "Qdrant vector store: not restored "
                "(no snapshot or Qdrant unreachable)"
            )
    except FileNotFoundError as e:
        raise click.ClickException(str(e))


@backup.command()
@click.option("--max-backups", default=10, help="Maximum auto-backups to keep")
def auto(max_backups: int) -> None:
    """Create an auto-backup and rotate old ones."""
    try:
        result = backup_ops.auto_backup(max_backups=max_backups)
        click.echo(f"Created auto-backup: {result.name}")
        if result.has_qdrant_snapshot:
            click.echo("Qdrant snapshot: included")
        else:
            click.echo("Qdrant snapshot: not included (Qdrant unreachable)")
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
