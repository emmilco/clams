"""Tests for CALM task CLI commands."""

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


class TestTaskCreate:
    """Tests for calm task create command."""

    def test_create_feature(self, cli_env: Path) -> None:
        """Test creating a feature task."""
        runner = CliRunner()
        result = runner.invoke(cli, ["task", "create", "SPEC-001", "Test Feature"])

        assert result.exit_code == 0
        assert "Created feature: SPEC-001" in result.output
        assert "phase: SPEC" in result.output

    def test_create_bug(self, cli_env: Path) -> None:
        """Test creating a bug task."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["task", "create", "BUG-001", "Test Bug", "--type", "bug"]
        )

        assert result.exit_code == 0
        assert "Created bug: BUG-001" in result.output
        assert "phase: REPORTED" in result.output


class TestTaskList:
    """Tests for calm task list command."""

    def test_list_empty(self, cli_env: Path) -> None:
        """Test listing when no tasks exist."""
        runner = CliRunner()
        result = runner.invoke(cli, ["task", "list"])

        assert result.exit_code == 0
        assert "No tasks found" in result.output

    def test_list_with_tasks(self, cli_env: Path) -> None:
        """Test listing tasks."""
        runner = CliRunner()

        # Create tasks
        runner.invoke(cli, ["task", "create", "SPEC-001", "Test 1"])
        runner.invoke(cli, ["task", "create", "SPEC-002", "Test 2"])

        result = runner.invoke(cli, ["task", "list"])

        assert result.exit_code == 0
        assert "SPEC-001" in result.output
        assert "SPEC-002" in result.output


class TestTaskShow:
    """Tests for calm task show command."""

    def test_show_task(self, cli_env: Path) -> None:
        """Test showing task details."""
        runner = CliRunner()

        # Create task
        runner.invoke(cli, ["task", "create", "SPEC-001", "Test Feature"])

        result = runner.invoke(cli, ["task", "show", "SPEC-001"])

        assert result.exit_code == 0
        assert "Task: SPEC-001" in result.output
        assert "Title: Test Feature" in result.output
        assert "Phase: SPEC" in result.output

    def test_show_nonexistent(self, cli_env: Path) -> None:
        """Test showing nonexistent task."""
        runner = CliRunner()
        result = runner.invoke(cli, ["task", "show", "NONEXISTENT"])

        assert result.exit_code != 0
        assert "not found" in result.output


class TestTaskTransition:
    """Tests for calm task transition command."""

    def test_transition_task(self, cli_env: Path) -> None:
        """Test transitioning a task."""
        runner = CliRunner()

        # Create and transition task
        runner.invoke(cli, ["task", "create", "SPEC-001", "Test"])
        result = runner.invoke(
            cli, ["task", "transition", "SPEC-001", "DESIGN", "--gate-result", "pass"]
        )

        assert result.exit_code == 0, result.output
        assert "Transitioned SPEC-001 to DESIGN" in result.output

    def test_invalid_transition(self, cli_env: Path) -> None:
        """Test invalid transition fails."""
        runner = CliRunner()

        # Create and try invalid transition
        runner.invoke(cli, ["task", "create", "SPEC-001", "Test"])
        result = runner.invoke(cli, ["task", "transition", "SPEC-001", "IMPLEMENT"])

        assert result.exit_code != 0
        assert "Invalid transition" in result.output
