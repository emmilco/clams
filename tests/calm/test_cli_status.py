"""Tests for CALM status CLI commands."""

from pathlib import Path

import pytest
from click.testing import CliRunner

import calm.config
import calm.orchestration.counters
import calm.orchestration.tasks
import calm.orchestration.workers
import calm.orchestration.reviews
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

    new_settings = CalmSettings(home=calm_home, db_path=db_path)
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

    # Mock server functions to avoid actual daemon checks
    monkeypatch.setattr(
        "calm.server.daemon.is_server_running",
        lambda: False,
    )
    monkeypatch.setattr(
        "calm.server.daemon.get_server_pid",
        lambda: None,
    )

    return db_path


class TestStatusMain:
    """Tests for calm status command."""

    def test_status_shows_overview(self, cli_env: Path) -> None:
        """Test that status shows system overview."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "CALM System Status" in result.output
        assert "Server" in result.output
        assert "Database" in result.output


class TestStatusHealth:
    """Tests for calm status health command."""

    def test_health_healthy(self, cli_env: Path) -> None:
        """Test health status when healthy."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "health"])

        assert result.exit_code == 0
        assert "System Health" in result.output
        assert "HEALTHY" in result.output

    def test_health_shows_counters(self, cli_env: Path) -> None:
        """Test that health shows counters."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "health"])

        assert result.exit_code == 0
        assert "merge_lock" in result.output
        assert "merges_since_e2e" in result.output


class TestStatusWorktrees:
    """Tests for calm status worktrees command."""

    def test_worktrees_empty(self, cli_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test worktrees status when none exist."""
        # Mock worktree list
        monkeypatch.setattr(
            "calm.orchestration.worktrees.list_worktrees",
            lambda **kwargs: [],
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["status", "worktrees"])

        assert result.exit_code == 0
        assert "No worktrees found" in result.output


class TestStatusTasks:
    """Tests for calm status tasks command."""

    def test_tasks_empty(self, cli_env: Path) -> None:
        """Test tasks status when none exist."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "tasks"])

        assert result.exit_code == 0
        assert "No active tasks" in result.output

    def test_tasks_with_tasks(self, cli_env: Path) -> None:
        """Test tasks status with tasks."""
        runner = CliRunner()

        # Create tasks
        runner.invoke(cli, ["task", "create", "SPEC-001", "Feature 1"])
        runner.invoke(cli, ["task", "create", "SPEC-002", "Feature 2"])

        result = runner.invoke(cli, ["status", "tasks"])

        assert result.exit_code == 0
        assert "SPEC-001" in result.output or "Feature 1" in result.output


class TestStatusWorkers:
    """Tests for calm status workers command."""

    def test_workers_empty(self, cli_env: Path) -> None:
        """Test workers status when none active."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "workers"])

        assert result.exit_code == 0
        assert "No active workers" in result.output

    def test_workers_with_workers(self, cli_env: Path) -> None:
        """Test workers status with active workers."""
        runner = CliRunner()

        # Create task and start worker
        runner.invoke(cli, ["task", "create", "SPEC-001", "Test"])
        runner.invoke(cli, ["worker", "start", "SPEC-001", "backend"])

        result = runner.invoke(cli, ["status", "workers"])

        assert result.exit_code == 0
        assert "backend" in result.output


class TestStatusCounters:
    """Tests for calm status counters command."""

    def test_counters(self, cli_env: Path) -> None:
        """Test counters status."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "counters"])

        assert result.exit_code == 0
        assert "System Counters" in result.output
        assert "merge_lock" in result.output
