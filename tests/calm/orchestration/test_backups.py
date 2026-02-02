"""Tests for CALM orchestration backups module."""

from pathlib import Path

import pytest

from calm.db.schema import init_database
from calm.orchestration.backups import (
    auto_backup,
    create_backup,
    delete_backup,
    list_backups,
    restore_backup,
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
    """Set up backup environment."""
    import calm.orchestration.backups
    from calm.config import CalmSettings

    calm_home = tmp_path / ".calm"
    new_settings = CalmSettings(home=calm_home, db_path=test_db)
    monkeypatch.setattr(calm.orchestration.backups, "settings", new_settings)

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
