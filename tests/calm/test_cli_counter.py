"""Tests for CALM counter CLI commands."""

from pathlib import Path

import pytest
from click.testing import CliRunner

import calm.config
import calm.orchestration.counters
from calm.cli.main import cli
from calm.config import CalmSettings
from calm.db.schema import init_database


@pytest.fixture
def cli_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up CLI environment with temp database."""
    calm_home = tmp_path / ".calm"
    calm_home.mkdir()

    db_path = calm_home / "metadata.db"
    init_database(db_path)

    monkeypatch.setenv("CALM_HOME", str(calm_home))
    monkeypatch.setenv("CALM_DB_PATH", str(db_path))

    new_settings = CalmSettings()
    monkeypatch.setattr(calm.config, "settings", new_settings)
    monkeypatch.setattr(calm.orchestration.counters, "settings", new_settings)

    return db_path


class TestCounterList:
    """Tests for calm counter list command."""

    def test_list_counters(self, cli_env: Path) -> None:
        """Test listing counters."""
        runner = CliRunner()
        result = runner.invoke(cli, ["counter", "list"])

        assert result.exit_code == 0
        assert "merge_lock" in result.output
        assert "merges_since_e2e" in result.output
        assert "merges_since_docs" in result.output


class TestCounterGet:
    """Tests for calm counter get command."""

    def test_get_counter(self, cli_env: Path) -> None:
        """Test getting a counter."""
        runner = CliRunner()
        result = runner.invoke(cli, ["counter", "get", "merge_lock"])

        assert result.exit_code == 0
        assert "0" in result.output


class TestCounterSet:
    """Tests for calm counter set command."""

    def test_set_counter(self, cli_env: Path) -> None:
        """Test setting a counter."""
        runner = CliRunner()

        # Set counter
        result = runner.invoke(cli, ["counter", "set", "merge_lock", "5"])
        assert result.exit_code == 0
        assert "Set merge_lock = 5" in result.output

        # Verify
        result = runner.invoke(cli, ["counter", "get", "merge_lock"])
        assert "5" in result.output


class TestCounterIncrement:
    """Tests for calm counter increment command."""

    def test_increment_counter(self, cli_env: Path) -> None:
        """Test incrementing a counter."""
        runner = CliRunner()

        result = runner.invoke(cli, ["counter", "increment", "merge_lock"])
        assert result.exit_code == 0
        assert "merge_lock = 1" in result.output

        result = runner.invoke(cli, ["counter", "increment", "merge_lock"])
        assert "merge_lock = 2" in result.output


class TestCounterReset:
    """Tests for calm counter reset command."""

    def test_reset_counter(self, cli_env: Path) -> None:
        """Test resetting a counter."""
        runner = CliRunner()

        # Set and reset
        runner.invoke(cli, ["counter", "set", "merge_lock", "10"])
        result = runner.invoke(cli, ["counter", "reset", "merge_lock"])

        assert result.exit_code == 0
        assert "Reset merge_lock to 0" in result.output


class TestCounterAdd:
    """Tests for calm counter add command."""

    def test_add_counter(self, cli_env: Path) -> None:
        """Test adding a new counter."""
        runner = CliRunner()

        result = runner.invoke(cli, ["counter", "add", "custom_counter", "5"])
        assert result.exit_code == 0
        assert "Created counter custom_counter = 5" in result.output

        # Verify
        result = runner.invoke(cli, ["counter", "get", "custom_counter"])
        assert "5" in result.output
