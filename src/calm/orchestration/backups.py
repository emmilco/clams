"""Backup management for CALM orchestration.

This module handles creating, listing, and restoring database backups.
Supports both SQLite metadata database and Qdrant vector store snapshots.

Qdrant snapshots use the native full-snapshot API to capture all collections
atomically. If Qdrant is unreachable, backups gracefully degrade to SQLite-only.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import httpx
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from calm.config import settings

logger = logging.getLogger(__name__)

# Suffix for Qdrant snapshot files alongside .db files
QDRANT_SNAPSHOT_SUFFIX = ".qdrant.snapshot"


@dataclass
class Backup:
    """Represents a database backup."""

    name: str
    path: Path
    created_at: datetime
    size_bytes: int
    has_qdrant_snapshot: bool = field(default=False)
    qdrant_snapshot_path: Path | None = field(default=None)


def _get_backups_dir() -> Path:
    """Get the backups directory, creating it if needed."""
    backups_dir = settings.home / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    return backups_dir


def _qdrant_snapshot_path_for(backup_name: str) -> Path:
    """Get the expected Qdrant snapshot path for a backup name."""
    return _get_backups_dir() / f"{backup_name}{QDRANT_SNAPSHOT_SUFFIX}"


async def create_qdrant_snapshot(
    qdrant_url: str,
    backup_name: str,
) -> Path | None:
    """Create a Qdrant full snapshot and download it locally.

    Creates a full snapshot of all Qdrant collections and downloads the
    snapshot file to the backups directory.

    Args:
        qdrant_url: URL of the Qdrant server (e.g. http://localhost:6333)
        backup_name: Name to use for the local snapshot file

    Returns:
        Path to the downloaded snapshot file, or None if Qdrant is unreachable
    """
    client: AsyncQdrantClient | None = None
    try:
        client = AsyncQdrantClient(url=qdrant_url, timeout=30)

        # Create a full snapshot (all collections atomically)
        snapshot_info = await client.create_full_snapshot(wait=True)
        if snapshot_info is None:
            logger.warning("Qdrant create_full_snapshot returned None")
            return None

        snapshot_name = snapshot_info.name

        # Download the snapshot file via HTTP
        dest_path = _qdrant_snapshot_path_for(backup_name)
        download_url = f"{qdrant_url}/snapshots/{snapshot_name}"

        async with httpx.AsyncClient(timeout=300.0) as http_client:
            response = await http_client.get(download_url)
            response.raise_for_status()
            dest_path.write_bytes(response.content)

        # Clean up the server-side snapshot to avoid accumulation
        try:
            await client.delete_full_snapshot(snapshot_name)
        except Exception:
            # Non-critical: server-side cleanup failure is OK
            logger.debug(
                "Could not delete server-side snapshot %s", snapshot_name
            )

        logger.info(
            "Qdrant snapshot saved: %s (%d bytes)",
            dest_path,
            dest_path.stat().st_size,
        )
        return dest_path

    except (
        ResponseHandlingException,
        UnexpectedResponse,
        httpx.ConnectError,
        httpx.TimeoutException,
        ConnectionError,
        OSError,
    ) as exc:
        logger.warning(
            "Qdrant unreachable, skipping vector store backup: %s", exc
        )
        return None
    finally:
        if client is not None:
            await client.close()


async def restore_qdrant_snapshot(
    qdrant_url: str,
    backup_name: str,
) -> bool:
    """Restore Qdrant data from a previously saved snapshot.

    Uploads the full snapshot file to Qdrant's snapshot recovery endpoint.

    Args:
        qdrant_url: URL of the Qdrant server
        backup_name: Name of the backup to restore from

    Returns:
        True if restored successfully, False if no snapshot file found
        or Qdrant is unreachable
    """
    snapshot_path = _qdrant_snapshot_path_for(backup_name)
    if not snapshot_path.exists():
        logger.info("No Qdrant snapshot file for backup '%s'", backup_name)
        return False

    try:
        upload_url = f"{qdrant_url}/snapshots/upload"
        snapshot_data = snapshot_path.read_bytes()

        async with httpx.AsyncClient(timeout=300.0) as http_client:
            response = await http_client.post(
                upload_url,
                content=snapshot_data,
                headers={"Content-Type": "application/octet-stream"},
            )
            response.raise_for_status()

        logger.info("Qdrant snapshot restored from %s", snapshot_path)
        return True

    except (
        httpx.ConnectError,
        httpx.TimeoutException,
        httpx.HTTPStatusError,
        ConnectionError,
        OSError,
    ) as exc:
        logger.warning(
            "Could not restore Qdrant snapshot: %s", exc
        )
        return False


async def _create_backup_async(
    name: str | None = None,
    db_path: Path | None = None,
    qdrant_url: str | None = None,
) -> Backup:
    """Async implementation of create_backup with Qdrant snapshot support.

    Args:
        name: Backup name (auto-generated if not provided)
        db_path: Path to database file (defaults to settings.db_path)
        qdrant_url: Qdrant server URL (defaults to settings.qdrant_url)

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

    if qdrant_url is None:
        qdrant_url = settings.qdrant_url

    backups_dir = _get_backups_dir()
    backup_path = backups_dir / f"{name}.db"

    # Copy SQLite database
    shutil.copy2(db_path, backup_path)

    # Attempt Qdrant snapshot
    qdrant_path = await create_qdrant_snapshot(qdrant_url, name)

    return Backup(
        name=name,
        path=backup_path,
        created_at=datetime.now(),
        size_bytes=backup_path.stat().st_size,
        has_qdrant_snapshot=qdrant_path is not None,
        qdrant_snapshot_path=qdrant_path,
    )


def create_backup(
    name: str | None = None,
    db_path: Path | None = None,
    qdrant_url: str | None = None,
) -> Backup:
    """Create a named backup of SQLite database and Qdrant vector store.

    Args:
        name: Backup name (auto-generated if not provided)
        db_path: Path to database file (defaults to settings.db_path)
        qdrant_url: Qdrant server URL (defaults to settings.qdrant_url)

    Returns:
        The created Backup

    Raises:
        FileNotFoundError: If database file not found
    """
    return asyncio.run(_create_backup_async(name, db_path, qdrant_url))


def list_backups() -> list[Backup]:
    """List available backups.

    Returns:
        List of backups sorted by creation time (newest first)
    """
    backups_dir = _get_backups_dir()
    backups: list[Backup] = []

    for backup_file in backups_dir.glob("*.db"):
        stat = backup_file.stat()
        qdrant_path = _qdrant_snapshot_path_for(backup_file.stem)
        has_qdrant = qdrant_path.exists()
        backups.append(
            Backup(
                name=backup_file.stem,
                path=backup_file,
                created_at=datetime.fromtimestamp(stat.st_mtime),
                size_bytes=stat.st_size,
                has_qdrant_snapshot=has_qdrant,
                qdrant_snapshot_path=qdrant_path if has_qdrant else None,
            )
        )

    # Sort by creation time, newest first
    backups.sort(key=lambda b: b.created_at, reverse=True)
    return backups


async def _restore_backup_async(
    name: str,
    db_path: Path | None = None,
    qdrant_url: str | None = None,
) -> bool:
    """Async implementation of restore_backup with Qdrant snapshot support.

    Args:
        name: Backup name to restore
        db_path: Path to restore to (defaults to settings.db_path)
        qdrant_url: Qdrant server URL (defaults to settings.qdrant_url)

    Returns:
        True if Qdrant snapshot was also restored, False if only SQLite

    Raises:
        FileNotFoundError: If backup not found
    """
    if db_path is None:
        db_path = settings.db_path

    if qdrant_url is None:
        qdrant_url = settings.qdrant_url

    backups_dir = _get_backups_dir()
    backup_path = backups_dir / f"{name}.db"

    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {name}")

    # Restore SQLite database
    shutil.copy2(backup_path, db_path)

    # Attempt Qdrant restore
    qdrant_restored = await restore_qdrant_snapshot(qdrant_url, name)
    return qdrant_restored


def restore_backup(
    name: str,
    db_path: Path | None = None,
    qdrant_url: str | None = None,
) -> bool:
    """Restore from a backup.

    Restores the SQLite database and, if a Qdrant snapshot exists, also
    restores the vector store data.

    Args:
        name: Backup name to restore
        db_path: Path to restore to (defaults to settings.db_path)
        qdrant_url: Qdrant server URL (defaults to settings.qdrant_url)

    Returns:
        True if Qdrant snapshot was also restored, False if only SQLite

    Raises:
        FileNotFoundError: If backup not found
    """
    return asyncio.run(_restore_backup_async(name, db_path, qdrant_url))


def auto_backup(
    max_backups: int = 10,
    db_path: Path | None = None,
    qdrant_url: str | None = None,
) -> Backup:
    """Create an auto-backup and rotate old ones.

    Keeps the last max_backups auto-backups. Both SQLite and Qdrant
    snapshot files are rotated together.

    Args:
        max_backups: Maximum number of auto-backups to keep
        db_path: Path to database file (defaults to settings.db_path)
        qdrant_url: Qdrant server URL (defaults to settings.qdrant_url)

    Returns:
        The created Backup
    """
    # Create auto-backup with timestamp
    name = f"auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup = create_backup(name, db_path, qdrant_url)

    # Get all auto-backups (by SQLite files)
    backups_dir = _get_backups_dir()
    auto_backups = sorted(
        backups_dir.glob("auto_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    # Remove old auto-backups (both SQLite and Qdrant snapshot files)
    for old_backup in auto_backups[max_backups:]:
        old_backup.unlink()
        # Also remove corresponding Qdrant snapshot if it exists
        qdrant_file = _qdrant_snapshot_path_for(old_backup.stem)
        if qdrant_file.exists():
            qdrant_file.unlink()

    return backup


def delete_backup(name: str) -> None:
    """Delete a backup.

    Removes both the SQLite backup file and the Qdrant snapshot file
    if it exists.

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

    # Also remove Qdrant snapshot if it exists
    qdrant_path = _qdrant_snapshot_path_for(name)
    if qdrant_path.exists():
        qdrant_path.unlink()
