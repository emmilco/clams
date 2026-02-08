"""Tests for CALM orchestration backups module."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from qdrant_client.http.models import SnapshotDescription

from calm.db.schema import init_database
from calm.orchestration.backups import (
    QDRANT_SNAPSHOT_SUFFIX,
    auto_backup,
    create_backup,
    create_qdrant_snapshot,
    delete_backup,
    list_backups,
    restore_backup,
    restore_qdrant_snapshot,
)


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Create a temporary test database."""
    # Create calm home structure
    calm_home = tmp_path / ".calm"
    calm_home.mkdir()

    db_path = calm_home / "metadata.db"
    init_database(db_path)
    return db_path


@pytest.fixture
def backup_setup(
    tmp_path: Path, test_db: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Set up backup environment with Qdrant mocked as unreachable."""
    import calm.orchestration.backups
    from calm.config import CalmSettings

    calm_home = tmp_path / ".calm"
    new_settings = CalmSettings(home=calm_home, db_path=test_db)
    monkeypatch.setattr(calm.orchestration.backups, "settings", new_settings)

    # Mock create_qdrant_snapshot to return None (Qdrant unreachable)
    # This prevents actual network calls in basic tests
    async def mock_create_qdrant_snapshot(
        qdrant_url: str, backup_name: str
    ) -> Path | None:
        return None

    monkeypatch.setattr(
        calm.orchestration.backups,
        "create_qdrant_snapshot",
        mock_create_qdrant_snapshot,
    )

    # Mock restore_qdrant_snapshot to return False
    async def mock_restore_qdrant_snapshot(
        qdrant_url: str, backup_name: str
    ) -> bool:
        return False

    monkeypatch.setattr(
        calm.orchestration.backups,
        "restore_qdrant_snapshot",
        mock_restore_qdrant_snapshot,
    )

    return test_db


@pytest.fixture
def backup_setup_with_qdrant(
    tmp_path: Path, test_db: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Set up backup environment with Qdrant mocked as available."""
    import calm.orchestration.backups
    from calm.config import CalmSettings

    calm_home = tmp_path / ".calm"
    new_settings = CalmSettings(home=calm_home, db_path=test_db)
    monkeypatch.setattr(calm.orchestration.backups, "settings", new_settings)

    # Mock create_qdrant_snapshot to create a fake snapshot directory
    async def mock_create_qdrant_snapshot(
        qdrant_url: str, backup_name: str
    ) -> Path | None:
        backups_dir = calm_home / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        snapshot_dir = backups_dir / f"{backup_name}{QDRANT_SNAPSHOT_SUFFIX}"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        # Create a couple of fake per-collection snapshot files
        (snapshot_dir / "memories.snapshot").write_bytes(b"fake-memories-data")
        (snapshot_dir / "ghap_full.snapshot").write_bytes(b"fake-ghap-data")
        return snapshot_dir

    monkeypatch.setattr(
        calm.orchestration.backups,
        "create_qdrant_snapshot",
        mock_create_qdrant_snapshot,
    )

    # Mock restore_qdrant_snapshot to return True if snapshot dir exists
    async def mock_restore_qdrant_snapshot(
        qdrant_url: str, backup_name: str
    ) -> bool:
        snapshot_dir = calm_home / "backups" / f"{backup_name}{QDRANT_SNAPSHOT_SUFFIX}"
        return snapshot_dir.exists() and snapshot_dir.is_dir()

    monkeypatch.setattr(
        calm.orchestration.backups,
        "restore_qdrant_snapshot",
        mock_restore_qdrant_snapshot,
    )

    return test_db


class TestCreateBackup:
    """Tests for create_backup function."""

    def test_create_backup_with_name(self, backup_setup: Path) -> None:
        """Test creating a named backup."""
        backup = create_backup(name="test_backup", db_path=backup_setup)

        assert backup.name == "test_backup"
        assert backup.path.exists()
        assert backup.size_bytes > 0

    def test_create_backup_auto_name(self, backup_setup: Path) -> None:
        """Test creating a backup with auto-generated name."""
        backup = create_backup(db_path=backup_setup)

        assert backup.name is not None
        assert len(backup.name) > 0
        assert backup.path.exists()

    def test_create_backup_nonexistent_db_raises(self, tmp_path: Path) -> None:
        """Test creating backup of nonexistent database raises error."""
        nonexistent = tmp_path / "nonexistent.db"

        with pytest.raises(FileNotFoundError):
            create_backup(db_path=nonexistent)


class TestListBackups:
    """Tests for list_backups function."""

    def test_list_backups_empty(self, backup_setup: Path) -> None:
        """Test listing backups when none exist."""
        backups = list_backups()
        assert backups == []

    def test_list_backups_after_create(self, backup_setup: Path) -> None:
        """Test listing backups after creating one."""
        create_backup(name="test1", db_path=backup_setup)
        create_backup(name="test2", db_path=backup_setup)

        backups = list_backups()
        assert len(backups) == 2


class TestRestoreBackup:
    """Tests for restore_backup function."""

    def test_restore_backup(self, backup_setup: Path) -> None:
        """Test restoring from a backup."""
        # Create backup
        create_backup(name="restore_test", db_path=backup_setup)

        # Modify the database (simulate changes)
        import sqlite3

        conn = sqlite3.connect(backup_setup)
        conn.execute("INSERT INTO counters (name, value) VALUES ('test_counter', 999)")
        conn.commit()
        conn.close()

        # Restore backup
        restore_backup("restore_test", db_path=backup_setup)

        # Check counter is back to original
        conn = sqlite3.connect(backup_setup)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM counters WHERE name = 'test_counter'")
        result = cursor.fetchone()
        conn.close()

        assert result is None  # Counter should not exist after restore

    def test_restore_nonexistent_backup_raises(self, backup_setup: Path) -> None:
        """Test restoring nonexistent backup raises error."""
        with pytest.raises(FileNotFoundError):
            restore_backup("nonexistent", db_path=backup_setup)


class TestAutoBackup:
    """Tests for auto_backup function."""

    def test_auto_backup_creates_backup(self, backup_setup: Path) -> None:
        """Test auto backup creates a backup."""
        backup = auto_backup(db_path=backup_setup)

        assert backup.name.startswith("auto_")
        assert backup.path.exists()

    def test_auto_backup_rotation(self, backup_setup: Path) -> None:
        """Test auto backup rotates old backups."""
        # Create more than max_backups
        for _ in range(5):
            auto_backup(max_backups=3, db_path=backup_setup)

        backups = list_backups()
        auto_backups = [b for b in backups if b.name.startswith("auto_")]

        assert len(auto_backups) <= 3


class TestDeleteBackup:
    """Tests for delete_backup function."""

    def test_delete_backup(self, backup_setup: Path) -> None:
        """Test deleting a backup."""
        create_backup(name="delete_me", db_path=backup_setup)
        delete_backup("delete_me")

        backups = list_backups()
        names = [b.name for b in backups]
        assert "delete_me" not in names

    def test_delete_nonexistent_backup_raises(self, backup_setup: Path) -> None:
        """Test deleting nonexistent backup raises error."""
        with pytest.raises(FileNotFoundError):
            delete_backup("nonexistent")


# ============================================================================
# Regression tests for BUG-078: Qdrant per-collection snapshot support
# ============================================================================


class TestQdrantSnapshotCreate:
    """Regression: backup includes Qdrant snapshot when Qdrant is available."""

    def test_backup_includes_qdrant_snapshot(
        self, backup_setup_with_qdrant: Path
    ) -> None:
        """BUG-078: Verify backup creates both SQLite and Qdrant snapshot dir."""
        backup = create_backup(name="with_qdrant", db_path=backup_setup_with_qdrant)

        assert backup.has_qdrant_snapshot is True
        assert backup.qdrant_snapshot_path is not None
        assert backup.qdrant_snapshot_path.exists()
        assert backup.qdrant_snapshot_path.is_dir()
        assert backup.path.exists()  # SQLite backup still exists

    def test_backup_without_qdrant_still_succeeds(
        self, backup_setup: Path
    ) -> None:
        """BUG-078: Verify backup works when Qdrant is unreachable."""
        backup = create_backup(name="no_qdrant", db_path=backup_setup)

        assert backup.has_qdrant_snapshot is False
        assert backup.qdrant_snapshot_path is None
        assert backup.path.exists()  # SQLite backup still created
        assert backup.size_bytes > 0


class TestQdrantSnapshotGracefulDegradation:
    """Regression: backup still succeeds when Qdrant is down."""

    def test_create_qdrant_snapshot_handles_connection_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BUG-078: create_qdrant_snapshot returns None on connection error."""
        import calm.orchestration.backups
        from calm.config import CalmSettings

        calm_home = tmp_path / ".calm"
        calm_home.mkdir()
        new_settings = CalmSettings(home=calm_home)
        monkeypatch.setattr(calm.orchestration.backups, "settings", new_settings)

        # Use a URL that will fail to connect
        result = asyncio.run(
            create_qdrant_snapshot("http://127.0.0.1:59999", "test_unreachable")
        )

        assert result is None

    def test_restore_qdrant_snapshot_handles_missing_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BUG-078: restore_qdrant_snapshot returns False when no snapshot dir."""
        import calm.orchestration.backups
        from calm.config import CalmSettings

        calm_home = tmp_path / ".calm"
        calm_home.mkdir()
        new_settings = CalmSettings(home=calm_home)
        monkeypatch.setattr(calm.orchestration.backups, "settings", new_settings)

        result = asyncio.run(
            restore_qdrant_snapshot("http://127.0.0.1:59999", "nonexistent")
        )

        assert result is False

    def test_restore_qdrant_snapshot_handles_connection_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BUG-078: restore_qdrant_snapshot returns False on connection error."""
        import calm.orchestration.backups
        from calm.config import CalmSettings

        calm_home = tmp_path / ".calm"
        calm_home.mkdir()
        new_settings = CalmSettings(home=calm_home)
        monkeypatch.setattr(calm.orchestration.backups, "settings", new_settings)

        # Create a fake snapshot directory with a snapshot file
        backups_dir = calm_home / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        snapshot_dir = backups_dir / f"conn_error{QDRANT_SNAPSHOT_SUFFIX}"
        snapshot_dir.mkdir()
        (snapshot_dir / "memories.snapshot").write_bytes(b"fake-data")

        result = asyncio.run(
            restore_qdrant_snapshot("http://127.0.0.1:59999", "conn_error")
        )

        assert result is False


class TestQdrantSnapshotRestore:
    """Regression: restore includes Qdrant restore when snapshot exists."""

    def test_restore_with_qdrant_snapshot(
        self, backup_setup_with_qdrant: Path
    ) -> None:
        """BUG-078: Verify restore restores both SQLite and Qdrant."""
        create_backup(name="restore_qdrant", db_path=backup_setup_with_qdrant)

        qdrant_restored = restore_backup(
            "restore_qdrant", db_path=backup_setup_with_qdrant
        )

        assert qdrant_restored is True

    def test_restore_without_qdrant_snapshot(
        self, backup_setup: Path
    ) -> None:
        """BUG-078: Verify restore works when no Qdrant snapshot exists."""
        create_backup(name="restore_no_qdrant", db_path=backup_setup)

        qdrant_restored = restore_backup(
            "restore_no_qdrant", db_path=backup_setup
        )

        assert qdrant_restored is False


class TestQdrantSnapshotAutoRotation:
    """Regression: auto-backup rotates Qdrant snapshots alongside SQLite."""

    def test_auto_backup_rotates_qdrant_snapshots(
        self, backup_setup_with_qdrant: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BUG-078: Verify old Qdrant snapshot dirs are cleaned up during rotation."""
        import time

        # Create more auto-backups than max_backups
        for i in range(5):
            auto_backup(max_backups=3, db_path=backup_setup_with_qdrant)
            # Small delay to ensure unique timestamps
            time.sleep(0.01)

        backups = list_backups()
        auto_backups = [b for b in backups if b.name.startswith("auto_")]

        # Should have at most 3 auto-backups
        assert len(auto_backups) <= 3

        # Count Qdrant snapshot directories in backups dir
        import calm.orchestration.backups

        backups_dir = calm.orchestration.backups.settings.home / "backups"
        qdrant_dirs = [
            d for d in backups_dir.iterdir()
            if d.is_dir() and d.name.startswith("auto_") and d.name.endswith(QDRANT_SNAPSHOT_SUFFIX)
        ]

        # Qdrant snapshot dir count should match auto-backup count
        assert len(qdrant_dirs) <= 3

    def test_auto_backup_with_qdrant_has_snapshot(
        self, backup_setup_with_qdrant: Path
    ) -> None:
        """BUG-078: Verify auto-backup includes Qdrant snapshot."""
        backup = auto_backup(db_path=backup_setup_with_qdrant)

        assert backup.has_qdrant_snapshot is True
        assert backup.qdrant_snapshot_path is not None
        assert backup.qdrant_snapshot_path.exists()
        assert backup.qdrant_snapshot_path.is_dir()


class TestQdrantSnapshotList:
    """Regression: list shows Qdrant snapshot status."""

    def test_list_shows_qdrant_status_true(
        self, backup_setup_with_qdrant: Path
    ) -> None:
        """BUG-078: Verify list_backups shows has_qdrant_snapshot=True."""
        create_backup(name="qdrant_yes", db_path=backup_setup_with_qdrant)

        backups = list_backups()
        assert len(backups) == 1
        assert backups[0].has_qdrant_snapshot is True
        assert backups[0].qdrant_snapshot_path is not None

    def test_list_shows_qdrant_status_false(
        self, backup_setup: Path
    ) -> None:
        """BUG-078: Verify list_backups shows has_qdrant_snapshot=False."""
        create_backup(name="qdrant_no", db_path=backup_setup)

        backups = list_backups()
        assert len(backups) == 1
        assert backups[0].has_qdrant_snapshot is False
        assert backups[0].qdrant_snapshot_path is None

    def test_list_mixed_qdrant_status(
        self,
        tmp_path: Path,
        test_db: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """BUG-078: List correctly shows mixed Qdrant snapshot status."""
        import calm.orchestration.backups
        from calm.config import CalmSettings

        calm_home = tmp_path / ".calm"
        new_settings = CalmSettings(home=calm_home, db_path=test_db)
        monkeypatch.setattr(calm.orchestration.backups, "settings", new_settings)

        # First backup: no Qdrant
        async def mock_no_qdrant(url: str, name: str) -> Path | None:
            return None

        monkeypatch.setattr(
            calm.orchestration.backups, "create_qdrant_snapshot", mock_no_qdrant
        )
        create_backup(name="without_qdrant", db_path=test_db)

        # Second backup: with Qdrant (directory-based)
        async def mock_with_qdrant(url: str, name: str) -> Path | None:
            backups_dir = calm_home / "backups"
            backups_dir.mkdir(parents=True, exist_ok=True)
            snapshot_dir = backups_dir / f"{name}{QDRANT_SNAPSHOT_SUFFIX}"
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            (snapshot_dir / "memories.snapshot").write_bytes(b"snapshot-data")
            return snapshot_dir

        monkeypatch.setattr(
            calm.orchestration.backups, "create_qdrant_snapshot", mock_with_qdrant
        )
        create_backup(name="with_qdrant", db_path=test_db)

        # List and verify mixed status
        backups = list_backups()
        by_name = {b.name: b for b in backups}

        assert by_name["without_qdrant"].has_qdrant_snapshot is False
        assert by_name["with_qdrant"].has_qdrant_snapshot is True


class TestQdrantSnapshotDelete:
    """Regression: delete removes Qdrant snapshot directories too."""

    def test_delete_removes_qdrant_snapshot(
        self, backup_setup_with_qdrant: Path
    ) -> None:
        """BUG-078: Verify delete removes both SQLite and Qdrant snapshot dir."""
        backup = create_backup(
            name="delete_both", db_path=backup_setup_with_qdrant
        )
        assert backup.qdrant_snapshot_path is not None
        qdrant_path = backup.qdrant_snapshot_path

        delete_backup("delete_both")

        assert not backup.path.exists()
        assert not qdrant_path.exists()


class TestCreateQdrantSnapshotUnit:
    """Unit tests for create_qdrant_snapshot with mock Qdrant client."""

    def test_create_qdrant_snapshot_per_collection(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BUG-078: create_qdrant_snapshot creates per-collection snapshots."""
        import calm.orchestration.backups
        from calm.config import CalmSettings

        calm_home = tmp_path / ".calm"
        calm_home.mkdir()
        new_settings = CalmSettings(home=calm_home)

        import importlib
        importlib.reload(calm.orchestration.backups)
        monkeypatch.setattr(calm.orchestration.backups, "settings", new_settings)

        # Mock collection listing: only 2 collections exist
        mock_collection_1 = MagicMock()
        mock_collection_1.name = "memories"
        mock_collection_2 = MagicMock()
        mock_collection_2.name = "ghap_full"
        mock_collections_response = MagicMock()
        mock_collections_response.collections = [mock_collection_1, mock_collection_2]

        mock_snapshot_desc = SnapshotDescription(
            name="memories-snap-2024.snapshot",
            size=4096,
            creation_time="2024-01-01T00:00:00",
        )

        mock_client = AsyncMock()
        mock_client.get_collections = AsyncMock(return_value=mock_collections_response)
        mock_client.create_snapshot = AsyncMock(return_value=mock_snapshot_desc)
        mock_client.delete_snapshot = AsyncMock(return_value=True)
        mock_client.close = AsyncMock()

        mock_http_response = MagicMock()
        mock_http_response.content = b"snapshot-binary-data"
        mock_http_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_http_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "calm.orchestration.backups.AsyncQdrantClient",
            return_value=mock_client,
        ), patch(
            "calm.orchestration.backups.httpx.AsyncClient",
            return_value=mock_http_client,
        ):
            result = asyncio.run(
                calm.orchestration.backups.create_qdrant_snapshot(
                    "http://localhost:6333", "test_snapshot"
                )
            )

        assert result is not None
        assert result.exists()
        assert result.is_dir()
        assert result.name == f"test_snapshot{QDRANT_SNAPSHOT_SUFFIX}"

        # Check per-collection snapshot files
        snapshot_files = sorted(result.glob("*.snapshot"))
        assert len(snapshot_files) == 2
        assert snapshot_files[0].name == "ghap_full.snapshot"
        assert snapshot_files[1].name == "memories.snapshot"

        # Verify create_snapshot was called per-collection
        assert mock_client.create_snapshot.call_count == 2

        # Verify download happened for each collection
        assert mock_http_client.get.call_count == 2

    def test_create_qdrant_snapshot_no_collections_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BUG-078: create_qdrant_snapshot returns None when no collections exist."""
        import calm.orchestration.backups
        from calm.config import CalmSettings

        calm_home = tmp_path / ".calm"
        calm_home.mkdir()
        new_settings = CalmSettings(home=calm_home)

        import importlib
        importlib.reload(calm.orchestration.backups)
        monkeypatch.setattr(calm.orchestration.backups, "settings", new_settings)

        # Mock empty collection listing
        mock_collections_response = MagicMock()
        mock_collections_response.collections = []

        mock_client = AsyncMock()
        mock_client.get_collections = AsyncMock(return_value=mock_collections_response)
        mock_client.close = AsyncMock()

        with patch(
            "calm.orchestration.backups.AsyncQdrantClient",
            return_value=mock_client,
        ):
            result = asyncio.run(
                calm.orchestration.backups.create_qdrant_snapshot(
                    "http://localhost:6333", "empty_test"
                )
            )

        assert result is None

    def test_create_qdrant_snapshot_skips_missing_collections(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BUG-078: Snapshot skips collections that don't exist in Qdrant."""
        import calm.orchestration.backups
        from calm.config import CalmSettings

        calm_home = tmp_path / ".calm"
        calm_home.mkdir()
        new_settings = CalmSettings(home=calm_home)

        import importlib
        importlib.reload(calm.orchestration.backups)
        monkeypatch.setattr(calm.orchestration.backups, "settings", new_settings)

        # Only 1 collection exists out of 8
        mock_collection = MagicMock()
        mock_collection.name = "memories"
        mock_collections_response = MagicMock()
        mock_collections_response.collections = [mock_collection]

        mock_snapshot_desc = SnapshotDescription(
            name="memories-snap.snapshot",
            size=1024,
            creation_time="2024-01-01T00:00:00",
        )

        mock_client = AsyncMock()
        mock_client.get_collections = AsyncMock(return_value=mock_collections_response)
        mock_client.create_snapshot = AsyncMock(return_value=mock_snapshot_desc)
        mock_client.delete_snapshot = AsyncMock(return_value=True)
        mock_client.close = AsyncMock()

        mock_http_response = MagicMock()
        mock_http_response.content = b"data"
        mock_http_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_http_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "calm.orchestration.backups.AsyncQdrantClient",
            return_value=mock_client,
        ), patch(
            "calm.orchestration.backups.httpx.AsyncClient",
            return_value=mock_http_client,
        ):
            result = asyncio.run(
                calm.orchestration.backups.create_qdrant_snapshot(
                    "http://localhost:6333", "partial_test"
                )
            )

        assert result is not None
        assert result.is_dir()

        # Only 1 snapshot file created (for memories)
        snapshot_files = list(result.glob("*.snapshot"))
        assert len(snapshot_files) == 1
        assert snapshot_files[0].name == "memories.snapshot"

        # create_snapshot called only once
        assert mock_client.create_snapshot.call_count == 1


class TestRestoreQdrantSnapshotUnit:
    """Unit tests for restore_qdrant_snapshot using per-collection upload."""

    def test_restore_calls_per_collection_upload(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BUG-078: restore uses POST /collections/{name}/snapshots/upload."""
        import calm.orchestration.backups
        from calm.config import CalmSettings

        calm_home = tmp_path / ".calm"
        calm_home.mkdir()
        new_settings = CalmSettings(home=calm_home)

        import importlib
        importlib.reload(calm.orchestration.backups)
        monkeypatch.setattr(calm.orchestration.backups, "settings", new_settings)

        # Create a fake snapshot directory with 2 collection snapshots
        backups_dir = calm_home / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        snapshot_dir = backups_dir / f"test_restore{QDRANT_SNAPSHOT_SUFFIX}"
        snapshot_dir.mkdir()
        (snapshot_dir / "memories.snapshot").write_bytes(b"memories-data")
        (snapshot_dir / "ghap_full.snapshot").write_bytes(b"ghap-data")

        mock_http_response = MagicMock()
        mock_http_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_http_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "calm.orchestration.backups.httpx.AsyncClient",
            return_value=mock_http_client,
        ):
            result = asyncio.run(
                calm.orchestration.backups.restore_qdrant_snapshot(
                    "http://localhost:6333", "test_restore"
                )
            )

        assert result is True

        # Verify POST was called for each collection
        assert mock_http_client.post.call_count == 2

        # Check the URLs used
        post_calls = mock_http_client.post.call_args_list
        urls = [call.args[0] for call in post_calls]
        assert "http://localhost:6333/collections/ghap_full/snapshots/upload" in urls
        assert "http://localhost:6333/collections/memories/snapshots/upload" in urls

    def test_restore_empty_snapshot_dir_returns_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BUG-078: restore returns False if snapshot dir has no files."""
        import calm.orchestration.backups
        from calm.config import CalmSettings

        calm_home = tmp_path / ".calm"
        calm_home.mkdir()
        new_settings = CalmSettings(home=calm_home)

        import importlib
        importlib.reload(calm.orchestration.backups)
        monkeypatch.setattr(calm.orchestration.backups, "settings", new_settings)

        # Create an empty snapshot directory
        backups_dir = calm_home / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        snapshot_dir = backups_dir / f"empty_restore{QDRANT_SNAPSHOT_SUFFIX}"
        snapshot_dir.mkdir()

        result = asyncio.run(
            calm.orchestration.backups.restore_qdrant_snapshot(
                "http://localhost:6333", "empty_restore"
            )
        )

        assert result is False
