"""Tests for CALM orchestration worktrees module."""

from pathlib import Path
from unittest import mock

import pytest

from calm.db.schema import init_database
from calm.orchestration.tasks import create_task
from calm.orchestration.worktrees import (
    WorktreeInfo,
    get_worktree_path,
)


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Create a temporary test database."""
    db_path = tmp_path / "test.db"
    init_database(db_path)
    return db_path


class TestWorktreeInfo:
    """Tests for WorktreeInfo dataclass."""

    def test_worktree_info_creation(self, tmp_path: Path) -> None:
        """Test creating a WorktreeInfo."""
        info = WorktreeInfo(
            task_id="SPEC-001",
            path=tmp_path / "worktree",
            branch="SPEC-001",
            task_type="feature",
            phase="IMPLEMENT",
        )

        assert info.task_id == "SPEC-001"
        assert info.branch == "SPEC-001"
        assert info.task_type == "feature"
        assert info.phase == "IMPLEMENT"

    def test_worktree_info_defaults(self, tmp_path: Path) -> None:
        """Test WorktreeInfo default values."""
        info = WorktreeInfo(
            task_id="SPEC-001",
            path=tmp_path,
            branch="main",
        )

        assert info.task_type is None
        assert info.phase is None


class TestGetWorktreePath:
    """Tests for get_worktree_path function."""

    def test_get_worktree_path_with_path(self, test_db: Path) -> None:
        """Test getting worktree path when set."""
        # Create task with worktree path
        from calm.orchestration.tasks import update_task

        create_task(
            task_id="SPEC-001",
            title="Test",
            project_path="/test/project",
            db_path=test_db,
        )

        update_task(
            "SPEC-001",
            worktree_path="/path/to/worktree",
            db_path=test_db,
        )

        path = get_worktree_path("SPEC-001", db_path=test_db)
        assert path == Path("/path/to/worktree")

    def test_get_worktree_path_not_set(self, test_db: Path) -> None:
        """Test getting worktree path when not set."""
        create_task(
            task_id="SPEC-001",
            title="Test",
            project_path="/test/project",
            db_path=test_db,
        )

        path = get_worktree_path("SPEC-001", db_path=test_db)
        assert path is None

    def test_get_worktree_path_nonexistent_task(self, test_db: Path) -> None:
        """Test getting worktree path for nonexistent task."""
        path = get_worktree_path("NONEXISTENT", db_path=test_db)
        assert path is None


# Note: Full integration tests for create_worktree, merge_worktree, etc.
# would require actual git repositories which are complex to set up.
# Those are better tested as integration tests in a real git environment.

class TestWorktreeCreateValidation:
    """Tests for worktree creation validation."""

    def test_create_worktree_requires_task(
        self, test_db: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that create_worktree requires an existing task."""
        from calm.orchestration.worktrees import create_worktree

        # Mock detect_main_repo to avoid needing a real git repo
        monkeypatch.setattr(
            "calm.orchestration.worktrees.detect_main_repo",
            lambda: "/fake/repo",
        )

        with pytest.raises(ValueError, match="not found"):
            create_worktree("NONEXISTENT", db_path=test_db)


class TestCheckMergeConflicts:
    """Tests for check_merge_conflicts function."""

    def test_check_merge_conflicts_mock(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test check_merge_conflicts with mocked subprocess."""
        from calm.orchestration.worktrees import check_merge_conflicts

        # Mock detect_main_repo
        monkeypatch.setattr(
            "calm.orchestration.worktrees.detect_main_repo",
            lambda: "/fake/repo",
        )

        # Mock subprocess to simulate no conflicts
        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with mock.patch("subprocess.run", return_value=mock_result):
            conflicts = check_merge_conflicts("SPEC-001")
            assert conflicts == []
