"""Backup management for CALM orchestration.

This module handles creating, listing, and restoring database backups.
"""

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from calm.config import settings


@dataclass
class Backup:
    """Represents a database backup."""

    name: str
    path: Path
    created_at: datetime
    size_bytes: int


def _get_backups_dir() -> Path:
    """Get the backups directory, creating it if needed."""
    backups_dir = settings.home / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    return backups_dir


def create_backup(
    name: str | None = None,
    db_path: Path | None = None,
) -> Backup:
    """Create a named backup.

    Args:
        name: Backup name (auto-generated if not provided)
        db_path: Path to database file (defaults to settings.db_path)

    Returns:
        The created Backup

    Raises:
        FileNotFoundError: If database file not found
    """
    if db_path is None:
        db_path = settings.db_path

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    if name is None:
        name = datetime.now().strftime("%Y%m%d_%H%M%S")

    backups_dir = _get_backups_dir()
    backup_path = backups_dir / f"{name}.db"

    shutil.copy2(db_path, backup_path)

    return Backup(
        name=name,
        path=backup_path,
        created_at=datetime.now(),
        size_bytes=backup_path.stat().st_size,
    )


def list_backups() -> list[Backup]:
    """List available backups.

    Returns:
        List of backups sorted by creation time (newest first)
    """
    backups_dir = _get_backups_dir()
    backups: list[Backup] = []

    for backup_file in backups_dir.glob("*.db"):
        stat = backup_file.stat()
        backups.append(
            Backup(
                name=backup_file.stem,
                path=backup_file,
                created_at=datetime.fromtimestamp(stat.st_mtime),
                size_bytes=stat.st_size,
            )
        )

    # Sort by creation time, newest first
    backups.sort(key=lambda b: b.created_at, reverse=True)
    return backups


def restore_backup(
    name: str,
    db_path: Path | None = None,
) -> None:
    """Restore from a backup.

    Args:
        name: Backup name to restore
        db_path: Path to restore to (defaults to settings.db_path)

    Raises:
        FileNotFoundError: If backup not found
    """
    if db_path is None:
        db_path = settings.db_path

    backups_dir = _get_backups_dir()
    backup_path = backups_dir / f"{name}.db"

    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {name}")

    # Copy backup to database path
    shutil.copy2(backup_path, db_path)


def auto_backup(
    max_backups: int = 10,
    db_path: Path | None = None,
) -> Backup:
    """Create an auto-backup and rotate old ones.

    Keeps the last max_backups auto-backups.

    Args:
        max_backups: Maximum number of auto-backups to keep
        db_path: Path to database file (defaults to settings.db_path)

    Returns:
        The created Backup
    """
    # Create auto-backup with timestamp
    name = f"auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup = create_backup(name, db_path)

    # Get all auto-backups
    backups_dir = _get_backups_dir()
    auto_backups = sorted(
        backups_dir.glob("auto_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    # Remove old auto-backups
    for old_backup in auto_backups[max_backups:]:
        old_backup.unlink()

    return backup


def delete_backup(name: str) -> None:
    """Delete a backup.

    Args:
        name: Backup name to delete

    Raises:
        FileNotFoundError: If backup not found
    """
    backups_dir = _get_backups_dir()
    backup_path = backups_dir / f"{name}.db"

    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {name}")

    backup_path.unlink()
