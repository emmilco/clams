"""Tests for CALM worktree CLI commands."""

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
from calm.orchestration.worktrees import WorktreeInfo


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
    # Note: worktrees module doesn't use settings directly

    # Mock project path detection
    monkeypatch.setattr(
        "calm.orchestration.project.detect_project_path",
        lambda: "/test/project",
    )

    return db_path


class TestWorktreeList:
    """Tests for calm worktree list command."""

    def test_list_worktrees_empty(
        self, cli_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test listing worktrees when none exist."""
        # Mock list_worktrees to return empty list
        monkeypatch.setattr(
            "calm.orchestration.worktrees.list_worktrees",
            lambda **kwargs: [],
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["worktree", "list"])

        assert result.exit_code == 0
        assert "No worktrees found" in result.output

    def test_list_worktrees_with_worktrees(
        self, cli_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test listing worktrees."""
        # Mock list_worktrees
        mock_worktrees = [
            WorktreeInfo(
                task_id="SPEC-001",
                path=Path("/test/.worktrees/SPEC-001"),
                branch="SPEC-001",
                task_type="feature",
                phase="IMPLEMENT",
            ),
        ]
        monkeypatch.setattr(
            "calm.orchestration.worktrees.list_worktrees",
            lambda **kwargs: mock_worktrees,
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["worktree", "list"])

        assert result.exit_code == 0
        assert "SPEC-001" in result.output


class TestWorktreePath:
    """Tests for calm worktree path command."""

    def test_path_with_worktree(
        self, cli_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test getting worktree path."""
        # Mock get_worktree_path
        monkeypatch.setattr(
            "calm.orchestration.worktrees.get_worktree_path",
            lambda task_id, **kwargs: Path("/test/.worktrees/SPEC-001"),
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["worktree", "path", "SPEC-001"])

        assert result.exit_code == 0
        assert "/test/.worktrees/SPEC-001" in result.output

    def test_path_no_worktree(
        self, cli_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test getting path when no worktree exists."""
        # Mock get_worktree_path to return None
        monkeypatch.setattr(
            "calm.orchestration.worktrees.get_worktree_path",
            lambda task_id, **kwargs: None,
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["worktree", "path", "SPEC-001"])

        assert result.exit_code != 0
        assert "No worktree found" in result.output


class TestWorktreeCreate:
    """Tests for calm worktree create command."""

    def test_create_worktree_no_task(self, cli_env: Path) -> None:
        """Test creating worktree for nonexistent task fails."""
        runner = CliRunner()
        result = runner.invoke(cli, ["worktree", "create", "NONEXISTENT"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()


class TestWorktreeCheckConflicts:
    """Tests for calm worktree check-conflicts command."""

    def test_check_conflicts_no_conflicts(
        self, cli_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test checking conflicts when none exist."""
        # Mock check_merge_conflicts
        monkeypatch.setattr(
            "calm.orchestration.worktrees.check_merge_conflicts",
            lambda task_id: [],
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["worktree", "check-conflicts", "SPEC-001"])

        assert result.exit_code == 0
        assert "No merge conflicts" in result.output

    def test_check_conflicts_with_conflicts(
        self, cli_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test checking conflicts when conflicts exist."""
        # Mock check_merge_conflicts
        monkeypatch.setattr(
            "calm.orchestration.worktrees.check_merge_conflicts",
            lambda task_id: ["file1.py", "file2.py"],
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["worktree", "check-conflicts", "SPEC-001"])

        assert result.exit_code == 1  # Should fail with conflicts
        assert "conflicts detected" in result.output.lower()
        assert "file1.py" in result.output
