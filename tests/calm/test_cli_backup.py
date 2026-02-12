"""Tests for CALM backup CLI commands."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

import calm.config
import calm.orchestration.backups
from calm.cli.main import cli
from calm.config import CalmSettings
from calm.db.schema import init_database
from calm.orchestration.backups import QDRANT_SNAPSHOT_SUFFIX


@pytest.fixture
def cli_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up CLI environment with temp database."""
    calm_home = tmp_path / ".calm"
    calm_home.mkdir()

    db_path = calm_home / "metadata.db"
    init_database(db_path)

    # Patch settings
    monkeypatch.setenv("CALM_HOME", str(calm_home))
    monkeypatch.setenv("CALM_DB_PATH", str(db_path))

    new_settings = CalmSettings(home=calm_home, db_path=db_path)
    monkeypatch.setattr(calm.config, "settings", new_settings)
    monkeypatch.setattr(calm.orchestration.backups, "settings", new_settings)

    # Mock create_qdrant_snapshot to return None (Qdrant unreachable)
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

    return db_path


@pytest.fixture
def cli_env_with_qdrant(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up CLI environment with Qdrant mocked as available."""
    calm_home = tmp_path / ".calm"
    calm_home.mkdir()

    db_path = calm_home / "metadata.db"
    init_database(db_path)

    # Patch settings
    monkeypatch.setenv("CALM_HOME", str(calm_home))
    monkeypatch.setenv("CALM_DB_PATH", str(db_path))

    new_settings = CalmSettings(home=calm_home, db_path=db_path)
    monkeypatch.setattr(calm.config, "settings", new_settings)
    monkeypatch.setattr(calm.orchestration.backups, "settings", new_settings)

    # Mock create_qdrant_snapshot to create a fake snapshot directory
    async def mock_create_qdrant_snapshot(
        qdrant_url: str, backup_name: str
    ) -> Path | None:
        backups_dir = calm_home / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        snapshot_dir = backups_dir / f"{backup_name}{QDRANT_SNAPSHOT_SUFFIX}"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        (snapshot_dir / "memories.snapshot").write_bytes(b"fake-data")
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

    return db_path


class TestBackupCreate:
    """Tests for calm backup create command."""

    def test_create_backup_with_name(self, cli_env: Path) -> None:
        """Test creating a named backup."""
        runner = CliRunner()
        result = runner.invoke(cli, ["backup", "create", "test_backup"])

        assert result.exit_code == 0
        assert "test_backup" in result.output
        assert "Created backup" in result.output

    def test_create_backup_auto_name(self, cli_env: Path) -> None:
        """Test creating a backup with auto-generated name."""
        runner = CliRunner()
        result = runner.invoke(cli, ["backup", "create"])

        assert result.exit_code == 0
        assert "Created backup" in result.output

    def test_create_backup_shows_qdrant_status(self, cli_env: Path) -> None:
        """Test create shows Qdrant unreachable when Qdrant is down."""
        runner = CliRunner()
        result = runner.invoke(cli, ["backup", "create", "test_no_qdrant"])

        assert result.exit_code == 0
        assert "Qdrant snapshot: not included" in result.output

    def test_create_backup_shows_qdrant_included(
        self, cli_env_with_qdrant: Path
    ) -> None:
        """Test create shows Qdrant snapshot when available."""
        runner = CliRunner()
        result = runner.invoke(cli, ["backup", "create", "test_with_qdrant"])

        assert result.exit_code == 0
        assert "Qdrant snapshot:" in result.output
        assert "not included" not in result.output


class TestBackupList:
    """Tests for calm backup list command."""

    def test_list_backups_empty(self, cli_env: Path) -> None:
        """Test listing backups when none exist."""
        runner = CliRunner()
        result = runner.invoke(cli, ["backup", "list"])

        assert result.exit_code == 0
        assert "No backups found" in result.output

    def test_list_backups_with_backups(self, cli_env: Path) -> None:
        """Test listing backups after creating some."""
        runner = CliRunner()

        # Create backups
        runner.invoke(cli, ["backup", "create", "backup1"])
        runner.invoke(cli, ["backup", "create", "backup2"])

        result = runner.invoke(cli, ["backup", "list"])

        assert result.exit_code == 0
        assert "backup1" in result.output
        assert "backup2" in result.output

    def test_list_shows_qdrant_column(self, cli_env: Path) -> None:
        """Test list output includes Qdrant column."""
        runner = CliRunner()
        runner.invoke(cli, ["backup", "create", "test_list"])

        result = runner.invoke(cli, ["backup", "list"])

        assert result.exit_code == 0
        assert "Qdrant" in result.output  # Column header


class TestBackupRestore:
    """Tests for calm backup restore command."""

    def test_restore_backup(self, cli_env: Path) -> None:
        """Test restoring a backup."""
        runner = CliRunner()

        # Create backup
        runner.invoke(cli, ["backup", "create", "restore_test"])

        # Restore with confirmation
        result = runner.invoke(
            cli, ["backup", "restore", "restore_test"], input="y\n"
        )

        assert result.exit_code == 0
        assert "Restored" in result.output

    def test_restore_nonexistent_backup(self, cli_env: Path) -> None:
        """Test restoring nonexistent backup fails."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["backup", "restore", "nonexistent"], input="y\n"
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_restore_shows_qdrant_status(self, cli_env: Path) -> None:
        """Test restore shows Qdrant restore status."""
        runner = CliRunner()
        runner.invoke(cli, ["backup", "create", "restore_status"])

        result = runner.invoke(
            cli, ["backup", "restore", "restore_status"], input="y\n"
        )

        assert result.exit_code == 0
        assert "Qdrant vector store:" in result.output


class TestBackupAuto:
    """Tests for calm backup auto command."""

    def test_auto_backup(self, cli_env: Path) -> None:
        """Test creating an auto-backup."""
        runner = CliRunner()
        result = runner.invoke(cli, ["backup", "auto"])

        assert result.exit_code == 0
        assert "auto_" in result.output

    def test_auto_backup_shows_qdrant_status(self, cli_env: Path) -> None:
        """Test auto-backup shows Qdrant snapshot status."""
        runner = CliRunner()
        result = runner.invoke(cli, ["backup", "auto"])

        assert result.exit_code == 0
        assert "Qdrant snapshot:" in result.output


class TestBackupDelete:
    """Tests for calm backup delete command."""

    def test_delete_backup(self, cli_env: Path) -> None:
        """Test deleting a backup."""
        runner = CliRunner()

        # Create backup
        runner.invoke(cli, ["backup", "create", "delete_me"])

        # Delete with confirmation
        result = runner.invoke(cli, ["backup", "delete", "delete_me"], input="y\n")

        assert result.exit_code == 0
        assert "Deleted" in result.output

    def test_delete_nonexistent_backup(self, cli_env: Path) -> None:
        """Test deleting nonexistent backup fails."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["backup", "delete", "nonexistent"], input="y\n"
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower()


# ============================================================================
# Tests for SPEC-059: CLI list shows count and configured limit
# ============================================================================


class TestBackupListCountLimit:
    """Tests that backup list shows count and configured limit."""

    def test_list_shows_count_and_max(self, cli_env: Path) -> None:
        """List output shows 'N of M backups (max: M)'."""
        runner = CliRunner()

        # Create 2 backups
        runner.invoke(cli, ["backup", "create", "cl_1"])
        runner.invoke(cli, ["backup", "create", "cl_2"])

        result = runner.invoke(cli, ["backup", "list"])

        assert result.exit_code == 0
        assert "2 of 10 backups (max: 10)" in result.output

    def test_list_empty_shows_max(self, cli_env: Path) -> None:
        """Empty list shows max configuration."""
        runner = CliRunner()
        result = runner.invoke(cli, ["backup", "list"])

        assert result.exit_code == 0
        assert "No backups found." in result.output
        assert "(max: 10)" in result.output

    def test_list_shows_custom_max(
        self, cli_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """List reflects custom max_backups setting."""
        import calm.cli.backup as cli_backup_mod
        from calm.config import CalmSettings

        # Need to patch settings in both calm.config AND calm.cli.backup
        # because the CLI module does: from calm.config import settings
        new_settings = CalmSettings(max_backups=25)
        monkeypatch.setattr(calm.config, "settings", new_settings)
        monkeypatch.setattr(cli_backup_mod, "settings", new_settings)

        runner = CliRunner()
        runner.invoke(cli, ["backup", "create", "custom_1"])

        result = runner.invoke(cli, ["backup", "list"])

        assert result.exit_code == 0
        assert "1 of 25 backups (max: 25)" in result.output
