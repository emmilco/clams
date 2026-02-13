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


class TestWorktreeCwdProtection:
    """Tests for BUG-089: refuse merge/remove when CWD is inside worktree."""

    def test_merge_refused_when_cwd_inside_worktree(
        self, cli_env: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Merge must fail if the shell's CWD is inside the target worktree."""
        main_repo = tmp_path / "repo"
        main_repo.mkdir()
        worktree_dir = main_repo / ".worktrees" / "TASK-001"
        worktree_dir.mkdir(parents=True)

        monkeypatch.setattr(
            "calm.cli.worktree.detect_main_repo", lambda: str(main_repo)
        )
        monkeypatch.chdir(worktree_dir)

        runner = CliRunner()
        result = runner.invoke(cli, ["worktree", "merge", "TASK-001"])

        assert result.exit_code != 0
        assert "Cannot proceed" in result.output
        assert str(main_repo) in result.output

    def test_merge_refused_when_cwd_in_subdirectory(
        self, cli_env: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Merge must also fail if CWD is in a subdirectory of the worktree."""
        main_repo = tmp_path / "repo"
        main_repo.mkdir()
        worktree_dir = main_repo / ".worktrees" / "TASK-002"
        sub_dir = worktree_dir / "src" / "deep"
        sub_dir.mkdir(parents=True)

        monkeypatch.setattr(
            "calm.cli.worktree.detect_main_repo", lambda: str(main_repo)
        )
        monkeypatch.chdir(sub_dir)

        runner = CliRunner()
        result = runner.invoke(cli, ["worktree", "merge", "TASK-002"])

        assert result.exit_code != 0
        assert "Cannot proceed" in result.output

    def test_merge_allowed_from_main_repo(
        self, cli_env: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Merge should proceed when CWD is the main repo (not inside worktree)."""
        main_repo = tmp_path / "repo"
        main_repo.mkdir()

        monkeypatch.setattr(
            "calm.cli.worktree.detect_main_repo", lambda: str(main_repo)
        )
        monkeypatch.chdir(main_repo)

        # Mock the actual merge operation to verify it gets called
        merge_called = False

        def mock_merge(*args: object, **kwargs: object) -> str:
            nonlocal merge_called
            merge_called = True
            return "abc123"

        monkeypatch.setattr(
            "calm.orchestration.worktrees.merge_worktree", mock_merge
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["worktree", "merge", "TASK-003"])

        assert result.exit_code == 0
        assert merge_called

    def test_remove_refused_when_cwd_inside_worktree(
        self, cli_env: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Remove must fail if the shell's CWD is inside the target worktree."""
        main_repo = tmp_path / "repo"
        main_repo.mkdir()
        worktree_dir = main_repo / ".worktrees" / "TASK-004"
        worktree_dir.mkdir(parents=True)

        monkeypatch.setattr(
            "calm.cli.worktree.detect_main_repo", lambda: str(main_repo)
        )
        monkeypatch.chdir(worktree_dir)

        runner = CliRunner()
        # --yes to skip confirmation prompt
        result = runner.invoke(cli, ["worktree", "remove", "TASK-004", "--yes"])

        assert result.exit_code != 0
        assert "Cannot proceed" in result.output

    def test_cwd_in_deleted_directory_refused(
        self, cli_env: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """If CWD is already a deleted directory, refuse with actionable message."""
        main_repo = tmp_path / "repo"
        main_repo.mkdir()

        monkeypatch.setattr(
            "calm.cli.worktree.detect_main_repo", lambda: str(main_repo)
        )

        # Simulate deleted CWD by making Path.cwd() raise OSError
        def broken_cwd() -> Path:
            raise OSError("No such file or directory")

        monkeypatch.setattr(Path, "cwd", staticmethod(broken_cwd))

        runner = CliRunner()
        result = runner.invoke(cli, ["worktree", "merge", "TASK-005"])

        assert result.exit_code != 0
        assert "deleted directory" in result.output


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
