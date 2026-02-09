"""Backup management for CALM orchestration.

This module handles creating, listing, and restoring database backups.
Supports both SQLite metadata database and Qdrant vector store snapshots.

Qdrant snapshots use the per-collection snapshot API to capture each collection
individually. If Qdrant is unreachable, backups gracefully degrade to SQLite-only.
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
from calm.search.collections import CollectionName

logger = logging.getLogger(__name__)

# Suffix for Qdrant snapshot directory alongside .db files
QDRANT_SNAPSHOT_SUFFIX = ".qdrant"

# All known collection names to snapshot
ALL_COLLECTIONS: list[str] = [
    CollectionName.MEMORIES,
    CollectionName.EXPERIENCES_FULL,
    CollectionName.EXPERIENCES_STRATEGY,
    CollectionName.EXPERIENCES_SURPRISE,
    CollectionName.EXPERIENCES_ROOT_CAUSE,
    CollectionName.VALUES,
    CollectionName.COMMITS,
    CollectionName.CODE,
]


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
    """Get the expected Qdrant snapshot directory for a backup name."""
    return _get_backups_dir() / f"{backup_name}{QDRANT_SNAPSHOT_SUFFIX}"


async def create_qdrant_snapshot(
    qdrant_url: str,
    backup_name: str,
) -> Path | None:
    """Create per-collection Qdrant snapshots and download them locally.

    Iterates over all known collections, creates a snapshot for each one
    that exists, and downloads the snapshot files to a subdirectory in
    the backups directory.

    Args:
        qdrant_url: URL of the Qdrant server (e.g. http://localhost:6333)
        backup_name: Name to use for the local snapshot directory

    Returns:
        Path to the snapshot directory, or None if Qdrant is unreachable
    """
    client: AsyncQdrantClient | None = None
    try:
        client = AsyncQdrantClient(url=qdrant_url, timeout=30)

        # Get existing collections to skip ones that have not been created
        collections_response = await client.get_collections()
        existing_names = {c.name for c in collections_response.collections}

        dest_dir = _qdrant_snapshot_path_for(backup_name)
        dest_dir.mkdir(parents=True, exist_ok=True)

        snapshot_count = 0
        for collection_name in ALL_COLLECTIONS:
            if collection_name not in existing_names:
                logger.debug(
                    "Collection '%s' does not exist, skipping", collection_name
                )
                continue

            # Create per-collection snapshot
            snapshot_info = await client.create_snapshot(
                collection_name=collection_name, wait=True
            )
            if snapshot_info is None:
                logger.warning(
                    "Qdrant create_snapshot returned None for '%s'",
                    collection_name,
                )
                continue

            snapshot_name = snapshot_info.name

            # Download the snapshot file via HTTP
            download_url = (
                f"{qdrant_url}/collections/{collection_name}"
                f"/snapshots/{snapshot_name}"
            )
            dest_path = dest_dir / f"{collection_name}.snapshot"

            async with httpx.AsyncClient(timeout=300.0) as http_client:
                response = await http_client.get(download_url)
                response.raise_for_status()
                dest_path.write_bytes(response.content)

            # Clean up server-side snapshot to avoid accumulation
            try:
                await client.delete_snapshot(
                    collection_name=collection_name,
                    snapshot_name=snapshot_name,
                )
            except Exception:
                logger.debug(
                    "Could not delete server-side snapshot %s for %s",
                    snapshot_name,
                    collection_name,
                )

            snapshot_count += 1

        if snapshot_count == 0:
            # No collections existed; clean up empty directory
            dest_dir.rmdir()
            logger.info("No Qdrant collections found to snapshot")
            return None

        logger.info(
            "Qdrant snapshots saved: %s (%d collections)",
            dest_dir,
            snapshot_count,
        )
        return dest_dir

    except (
        ResponseHandlingException,
        UnexpectedResponse,
        httpx.ConnectError,
        httpx.TimeoutException,
        httpx.HTTPStatusError,
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
    """Restore Qdrant data from previously saved per-collection snapshots.

    For each snapshot file in the backup directory, uploads it to the
    corresponding collection per-collection snapshot upload endpoint.

    Args:
        qdrant_url: URL of the Qdrant server
        backup_name: Name of the backup to restore from

    Returns:
        True if at least one collection was restored successfully,
        False if no snapshot directory found or Qdrant is unreachable
    """
    snapshot_dir = _qdrant_snapshot_path_for(backup_name)
    if not snapshot_dir.exists() or not snapshot_dir.is_dir():
        logger.info("No Qdrant snapshot directory for backup '%s'", backup_name)
        return False

    try:
        restored_count = 0
        for snapshot_file in sorted(snapshot_dir.glob("*.snapshot")):
            # Derive collection name from filename
            # e.g. "memories.snapshot" -> "memories"
            collection_name = snapshot_file.stem

            upload_url = (
                f"{qdrant_url}/collections/{collection_name}/snapshots/upload"
            )

            async with httpx.AsyncClient(timeout=300.0) as http_client:
                snapshot_data = snapshot_file.read_bytes()
                response = await http_client.post(
                    upload_url,
                    files={
                        "snapshot": (
                            snapshot_file.name,
                            snapshot_data,
                            "application/octet-stream",
                        )
                    },
                )
                response.raise_for_status()

            logger.info(
                "Restored collection '%s' from %s",
                collection_name,
                snapshot_file,
            )
            restored_count += 1

        if restored_count > 0:
            logger.info(
                "Qdrant restore complete: %d collections from %s",
                restored_count,
                snapshot_dir,
            )
            return True

        return False

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
        has_qdrant = qdrant_path.exists() and qdrant_path.is_dir()
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
    snapshot directories are rotated together.

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

    # Remove old auto-backups (both SQLite and Qdrant snapshot directories)
    for old_backup in auto_backups[max_backups:]:
        old_backup.unlink()
        # Also remove corresponding Qdrant snapshot directory if it exists
        qdrant_dir = _qdrant_snapshot_path_for(old_backup.stem)
        if qdrant_dir.exists() and qdrant_dir.is_dir():
            shutil.rmtree(qdrant_dir)

    return backup


def delete_backup(name: str) -> None:
    """Delete a backup.

    Removes both the SQLite backup file and the Qdrant snapshot directory
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

    # Also remove Qdrant snapshot directory if it exists
    qdrant_path = _qdrant_snapshot_path_for(name)
    if qdrant_path.exists() and qdrant_path.is_dir():
        shutil.rmtree(qdrant_path)
