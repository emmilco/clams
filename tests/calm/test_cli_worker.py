"""Tests for CALM worker CLI commands."""

from pathlib import Path

import pytest
from click.testing import CliRunner

import calm.config
import calm.orchestration.counters
import calm.orchestration.reviews
import calm.orchestration.tasks
import calm.orchestration.workers
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

    # Patch settings
    monkeypatch.setenv("CALM_HOME", str(calm_home))
    monkeypatch.setenv("CALM_DB_PATH", str(db_path))

    new_settings = CalmSettings()
    monkeypatch.setattr(calm.config, "settings", new_settings)

    # Patch settings in all orchestration modules that use it
    monkeypatch.setattr(calm.orchestration.counters, "settings", new_settings)
    monkeypatch.setattr(calm.orchestration.tasks, "settings", new_settings)
    monkeypatch.setattr(calm.orchestration.workers, "settings", new_settings)
    monkeypatch.setattr(calm.orchestration.reviews, "settings", new_settings)

    # Mock project path detection
    monkeypatch.setattr(
        "calm.orchestration.project.detect_project_path",
        lambda: "/test/project",
    )

    return db_path


class TestWorkerStart:
    """Tests for calm worker start command."""

    def test_start_worker(self, cli_env: Path) -> None:
        """Test starting a worker."""
        runner = CliRunner()

        # Create task first
        runner.invoke(cli, ["task", "create", "SPEC-001", "Test"])

        # Start worker
        result = runner.invoke(cli, ["worker", "start", "SPEC-001", "backend"])

        assert result.exit_code == 0
        # Should output the worker ID
        assert result.output.strip().startswith("W-")


class TestWorkerComplete:
    """Tests for calm worker complete command."""

    def test_complete_worker(self, cli_env: Path) -> None:
        """Test completing a worker."""
        runner = CliRunner()

        # Create task and start worker
        runner.invoke(cli, ["task", "create", "SPEC-001", "Test"])
        start_result = runner.invoke(cli, ["worker", "start", "SPEC-001", "backend"])
        worker_id = start_result.output.strip()

        # Complete worker
        result = runner.invoke(cli, ["worker", "complete", worker_id])

        assert result.exit_code == 0
        assert "completed" in result.output.lower()

    def test_complete_nonexistent_worker(self, cli_env: Path) -> None:
        """Test completing nonexistent worker fails."""
        runner = CliRunner()
        result = runner.invoke(cli, ["worker", "complete", "W-nonexistent"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()


class TestWorkerFail:
    """Tests for calm worker fail command."""

    def test_fail_worker(self, cli_env: Path) -> None:
        """Test failing a worker."""
        runner = CliRunner()

        # Create task and start worker
        runner.invoke(cli, ["task", "create", "SPEC-001", "Test"])
        start_result = runner.invoke(cli, ["worker", "start", "SPEC-001", "backend"])
        worker_id = start_result.output.strip()

        # Fail worker
        result = runner.invoke(cli, ["worker", "fail", worker_id])

        assert result.exit_code == 0
        assert "failed" in result.output.lower()


class TestWorkerList:
    """Tests for calm worker list command."""

    def test_list_workers_empty(self, cli_env: Path) -> None:
        """Test listing workers when none exist."""
        runner = CliRunner()
        result = runner.invoke(cli, ["worker", "list"])

        assert result.exit_code == 0
        assert "No workers found" in result.output

    def test_list_workers_with_workers(self, cli_env: Path) -> None:
        """Test listing workers."""
        runner = CliRunner()

        # Create task and start workers
        runner.invoke(cli, ["task", "create", "SPEC-001", "Test"])
        runner.invoke(cli, ["worker", "start", "SPEC-001", "backend"])
        runner.invoke(cli, ["worker", "start", "SPEC-001", "reviewer"])

        result = runner.invoke(cli, ["worker", "list"])

        assert result.exit_code == 0
        assert "backend" in result.output
        assert "reviewer" in result.output

    def test_list_workers_by_status(self, cli_env: Path) -> None:
        """Test listing workers filtered by status."""
        runner = CliRunner()

        # Create task and start workers
        runner.invoke(cli, ["task", "create", "SPEC-001", "Test"])
        start_result = runner.invoke(cli, ["worker", "start", "SPEC-001", "backend"])
        worker_id = start_result.output.strip()

        # Complete one worker
        runner.invoke(cli, ["worker", "complete", worker_id])

        # List only active workers
        result = runner.invoke(cli, ["worker", "list", "--status", "active"])

        assert result.exit_code == 0
        # The completed worker should not appear


class TestWorkerCleanup:
    """Tests for calm worker cleanup command."""

    def test_cleanup_workers(self, cli_env: Path) -> None:
        """Test cleaning up stale workers."""
        runner = CliRunner()
        result = runner.invoke(cli, ["worker", "cleanup"])

        assert result.exit_code == 0
        assert "stale workers" in result.output.lower()
