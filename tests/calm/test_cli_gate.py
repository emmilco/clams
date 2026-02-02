"""Tests for CALM gate CLI commands."""

from pathlib import Path

import pytest
from click.testing import CliRunner

import calm.config
import calm.orchestration.counters
import calm.orchestration.tasks
import calm.orchestration.workers
import calm.orchestration.reviews
import calm.orchestration.gates
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
    monkeypatch.setattr(calm.orchestration.gates, "settings", new_settings)

    # Mock project path detection
    monkeypatch.setattr(
        "calm.orchestration.project.detect_project_path",
        lambda: "/test/project",
    )

    return db_path


class TestGateList:
    """Tests for calm gate list command."""

    def test_list_gates(self, cli_env: Path) -> None:
        """Test listing gate requirements."""
        runner = CliRunner()
        result = runner.invoke(cli, ["gate", "list"])

        assert result.exit_code == 0
        assert "Gate Requirements" in result.output
        assert "IMPLEMENT-CODE_REVIEW" in result.output
        assert "Tests pass" in result.output or "tests_pass" in result.output


class TestGateCheck:
    """Tests for calm gate check command."""

    def test_gate_check_no_worktree(self, cli_env: Path) -> None:
        """Test gate check fails when no worktree exists."""
        runner = CliRunner()

        # Create task without worktree
        runner.invoke(cli, ["task", "create", "SPEC-001", "Test"])

        result = runner.invoke(
            cli, ["gate", "check", "SPEC-001", "IMPLEMENT-CODE_REVIEW"]
        )

        assert result.exit_code != 0
        assert "worktree" in result.output.lower() or "error" in result.output.lower()

    def test_gate_check_nonexistent_task(self, cli_env: Path) -> None:
        """Test gate check fails for nonexistent task."""
        runner = CliRunner()

        result = runner.invoke(
            cli, ["gate", "check", "NONEXISTENT", "IMPLEMENT-CODE_REVIEW"]
        )

        assert result.exit_code != 0
