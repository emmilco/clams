"""Tests for CALM orchestration tasks module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from calm.db.schema import init_database
from calm.orchestration.tasks import (
    create_task,
    delete_task,
    get_next_task_id,
    get_task,
    list_tasks,
    transition_task,
    update_task,
)


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Create a temporary test database."""
    db_path = tmp_path / "test.db"
    init_database(db_path)
    return db_path


class TestCreateTask:
    """Tests for create_task function."""

    def test_create_feature_task(self, test_db: Path) -> None:
        """Test creating a feature task."""
        task = create_task(
            task_id="SPEC-001",
            title="Test Feature",
            task_type="feature",
            project_path="/test/project",
            db_path=test_db,
        )

        assert task.id == "SPEC-001"
        assert task.title == "Test Feature"
        assert task.task_type == "feature"
        assert task.phase == "SPEC"
        assert task.project_path == "/test/project"

    def test_create_bug_task(self, test_db: Path) -> None:
        """Test creating a bug task."""
        task = create_task(
            task_id="BUG-001",
            title="Test Bug",
            task_type="bug",
            project_path="/test/project",
            db_path=test_db,
        )

        assert task.id == "BUG-001"
        assert task.task_type == "bug"
        assert task.phase == "REPORTED"

    def test_create_task_with_spec_id(self, test_db: Path) -> None:
        """Test creating a subtask with spec_id."""
        # Create parent first
        create_task(
            task_id="SPEC-001",
            title="Parent Spec",
            project_path="/test/project",
            db_path=test_db,
        )

        # Create subtask
        task = create_task(
            task_id="SPEC-001-01",
            title="Subtask",
            spec_id="SPEC-001",
            project_path="/test/project",
            db_path=test_db,
        )

        assert task.spec_id == "SPEC-001"

    def test_duplicate_task_raises(self, test_db: Path) -> None:
        """Test that creating duplicate task raises error."""
        create_task(
            task_id="SPEC-001",
            title="Test",
            project_path="/test/project",
            db_path=test_db,
        )

        with pytest.raises(ValueError, match="already exists"):
            create_task(
                task_id="SPEC-001",
                title="Duplicate",
                project_path="/test/project",
                db_path=test_db,
            )


class TestGetTask:
    """Tests for get_task function."""

    def test_get_existing_task(self, test_db: Path) -> None:
        """Test getting an existing task."""
        create_task(
            task_id="SPEC-001",
            title="Test",
            project_path="/test/project",
            db_path=test_db,
        )

        task = get_task("SPEC-001", db_path=test_db)
        assert task is not None
        assert task.id == "SPEC-001"

    def test_get_nonexistent_task(self, test_db: Path) -> None:
        """Test getting a nonexistent task returns None."""
        task = get_task("NONEXISTENT", db_path=test_db)
        assert task is None


class TestListTasks:
    """Tests for list_tasks function."""

    def test_list_tasks_empty(self, test_db: Path) -> None:
        """Test listing tasks when none exist."""
        tasks = list_tasks(project_path="/test/project", db_path=test_db)
        assert tasks == []

    def test_list_tasks_by_phase(self, test_db: Path) -> None:
        """Test filtering tasks by phase."""
        create_task(
            task_id="SPEC-001",
            title="Test 1",
            project_path="/test/project",
            db_path=test_db,
        )
        create_task(
            task_id="SPEC-002",
            title="Test 2",
            project_path="/test/project",
            db_path=test_db,
        )

        tasks = list_tasks(phase="SPEC", project_path="/test/project", db_path=test_db)
        assert len(tasks) == 2

    def test_list_tasks_by_type(self, test_db: Path) -> None:
        """Test filtering tasks by type."""
        create_task(
            task_id="SPEC-001",
            title="Feature",
            task_type="feature",
            project_path="/test/project",
            db_path=test_db,
        )
        create_task(
            task_id="BUG-001",
            title="Bug",
            task_type="bug",
            project_path="/test/project",
            db_path=test_db,
        )

        features = list_tasks(
            task_type="feature", project_path="/test/project", db_path=test_db
        )
        bugs = list_tasks(
            task_type="bug", project_path="/test/project", db_path=test_db
        )

        assert len(features) == 1
        assert len(bugs) == 1


class TestUpdateTask:
    """Tests for update_task function."""

    def test_update_specialist(self, test_db: Path) -> None:
        """Test updating specialist."""
        create_task(
            task_id="SPEC-001",
            title="Test",
            project_path="/test/project",
            db_path=test_db,
        )

        task = update_task("SPEC-001", specialist="backend", db_path=test_db)
        assert task.specialist == "backend"

    def test_update_notes(self, test_db: Path) -> None:
        """Test updating notes."""
        create_task(
            task_id="SPEC-001",
            title="Test",
            project_path="/test/project",
            db_path=test_db,
        )

        task = update_task("SPEC-001", notes="Some notes", db_path=test_db)
        assert task.notes == "Some notes"

    def test_update_blocked_by(self, test_db: Path) -> None:
        """Test updating blocked_by list."""
        create_task(
            task_id="SPEC-001",
            title="Test",
            project_path="/test/project",
            db_path=test_db,
        )

        task = update_task(
            "SPEC-001", blocked_by=["SPEC-002", "SPEC-003"], db_path=test_db
        )
        assert task.blocked_by == ["SPEC-002", "SPEC-003"]

    def test_update_nonexistent_raises(self, test_db: Path) -> None:
        """Test updating nonexistent task raises error."""
        with pytest.raises(ValueError, match="not found"):
            update_task("NONEXISTENT", notes="test", db_path=test_db)


class TestTransitionTask:
    """Tests for transition_task function."""

    def test_valid_feature_transition(self, test_db: Path) -> None:
        """Test valid feature phase transition."""
        create_task(
            task_id="SPEC-001",
            title="Test",
            project_path="/test/project",
            db_path=test_db,
        )

        task = transition_task(
            "SPEC-001", "DESIGN", gate_result="pass", db_path=test_db
        )
        assert task.phase == "DESIGN"

    def test_valid_bug_transition(self, test_db: Path) -> None:
        """Test valid bug phase transition."""
        create_task(
            task_id="BUG-001",
            title="Test Bug",
            task_type="bug",
            project_path="/test/project",
            db_path=test_db,
        )

        task = transition_task(
            "BUG-001", "INVESTIGATED", gate_result="pass", db_path=test_db
        )
        assert task.phase == "INVESTIGATED"

    def test_invalid_transition_raises(self, test_db: Path) -> None:
        """Test that invalid transition raises error."""
        create_task(
            task_id="SPEC-001",
            title="Test",
            project_path="/test/project",
            db_path=test_db,
        )

        with pytest.raises(ValueError, match="Invalid transition"):
            transition_task("SPEC-001", "IMPLEMENT", db_path=test_db)

    def test_transition_nonexistent_raises(self, test_db: Path) -> None:
        """Test transitioning nonexistent task raises error."""
        with pytest.raises(ValueError, match="not found"):
            transition_task("NONEXISTENT", "DESIGN", db_path=test_db)


class TestDeleteTask:
    """Tests for delete_task function."""

    def test_delete_task(self, test_db: Path) -> None:
        """Test deleting a task."""
        create_task(
            task_id="SPEC-001",
            title="Test",
            project_path="/test/project",
            db_path=test_db,
        )

        delete_task("SPEC-001", db_path=test_db)

        task = get_task("SPEC-001", db_path=test_db)
        assert task is None

    def test_delete_nonexistent_raises(self, test_db: Path) -> None:
        """Test deleting nonexistent task raises error."""
        with pytest.raises(ValueError, match="not found"):
            delete_task("NONEXISTENT", db_path=test_db)


class TestListTasksIncludeDone:
    """Regression tests for include_done filtering."""

    def test_exclude_done_by_default(self, test_db: Path) -> None:
        """Test that DONE tasks are excluded by default."""
        # Create a task and transition it to DONE
        create_task(
            task_id="SPEC-001",
            title="Done Task",
            project_path="/test/project",
            db_path=test_db,
        )
        # Manually set phase to DONE via update
        from calm.orchestration.tasks import update_task

        update_task("SPEC-001", phase="DONE", db_path=test_db)

        # Create an active task
        create_task(
            task_id="SPEC-002",
            title="Active Task",
            project_path="/test/project",
            db_path=test_db,
        )

        tasks = list_tasks(project_path="/test/project", db_path=test_db)
        assert len(tasks) == 1
        assert tasks[0].id == "SPEC-002"

    def test_include_done_returns_all(self, test_db: Path) -> None:
        """Test that include_done=True returns DONE tasks too."""
        create_task(
            task_id="SPEC-001",
            title="Done Task",
            project_path="/test/project",
            db_path=test_db,
        )
        from calm.orchestration.tasks import update_task

        update_task("SPEC-001", phase="DONE", db_path=test_db)

        create_task(
            task_id="SPEC-002",
            title="Active Task",
            project_path="/test/project",
            db_path=test_db,
        )

        tasks = list_tasks(
            project_path="/test/project",
            include_done=True,
            db_path=test_db,
        )
        assert len(tasks) == 2
        ids = {t.id for t in tasks}
        assert ids == {"SPEC-001", "SPEC-002"}


class TestListTasksWorktreeProjectPath:
    """Regression tests for worktree project path resolution.

    When running from a worktree, detect_main_repo() should return the
    main repo path so that tasks stored under that path are found.
    """

    def test_list_tasks_uses_main_repo_path(self, test_db: Path) -> None:
        """Test that list_tasks auto-detects main repo path, not worktree path."""
        main_repo = "/test/project"
        create_task(
            task_id="BUG-001",
            title="Test Bug",
            task_type="bug",
            project_path=main_repo,
            db_path=test_db,
        )

        # Simulate calling from a worktree: detect_main_repo returns main path
        with patch(
            "calm.orchestration.tasks.detect_main_repo", return_value=main_repo
        ):
            tasks = list_tasks(db_path=test_db)

        assert len(tasks) == 1
        assert tasks[0].id == "BUG-001"

    def test_list_tasks_worktree_path_returns_empty(self, test_db: Path) -> None:
        """Test that using worktree path (not main repo) returns no results."""
        main_repo = "/test/project"
        worktree_path = "/test/project/.worktrees/BUG-001"

        create_task(
            task_id="BUG-001",
            title="Test Bug",
            task_type="bug",
            project_path=main_repo,
            db_path=test_db,
        )

        # Explicitly pass worktree path -- should find nothing
        tasks = list_tasks(project_path=worktree_path, db_path=test_db)
        assert len(tasks) == 0

    def test_create_task_uses_main_repo_path(self, test_db: Path) -> None:
        """Test that create_task auto-detects main repo path, not worktree path."""
        main_repo = "/test/project"

        with patch(
            "calm.orchestration.tasks.detect_main_repo", return_value=main_repo
        ):
            task = create_task(
                task_id="BUG-002",
                title="Created from worktree",
                task_type="bug",
                db_path=test_db,
            )

        assert task.project_path == main_repo


class TestRowToTaskBlockedByParsing:
    """Regression tests for BUG-074: malformed blocked_by values.

    The blocked_by column should contain JSON arrays (e.g., '["SPEC-001"]'),
    but corrupted data (bare strings without JSON serialization) was written
    by a path that bypassed json.dumps(). The _row_to_task() function must
    handle these gracefully instead of crashing with JSONDecodeError.
    """

    def _insert_task_with_blocked_by(
        self, db_path: Path, task_id: str, blocked_by_value: str | None
    ) -> None:
        """Insert a task with a specific raw blocked_by value via direct SQL."""
        import sqlite3
        from datetime import datetime

        conn = sqlite3.connect(db_path)
        now = datetime.now().isoformat()
        conn.execute(
            """
            INSERT INTO tasks (
                id, title, task_type, phase, blocked_by,
                project_path, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, "Test", "feature", "DONE", blocked_by_value,
             "/test/project", now, now),
        )
        conn.commit()
        conn.close()

    def test_bare_string_blocked_by(self, test_db: Path) -> None:
        """Test that a bare string blocked_by (no JSON) is parsed correctly."""
        self._insert_task_with_blocked_by(test_db, "SPEC-100", "SPEC-058-01")

        tasks = list_tasks(
            project_path="/test/project", include_done=True, db_path=test_db
        )
        task = next(t for t in tasks if t.id == "SPEC-100")
        assert task.blocked_by == ["SPEC-058-01"]

    def test_comma_separated_blocked_by(self, test_db: Path) -> None:
        """Test that comma-separated bare strings are parsed correctly."""
        self._insert_task_with_blocked_by(
            test_db, "SPEC-101", "SPEC-001, SPEC-002"
        )

        task = get_task("SPEC-101", project_path="/test/project", db_path=test_db)
        assert task is not None
        assert task.blocked_by == ["SPEC-001", "SPEC-002"]

    def test_valid_json_blocked_by(self, test_db: Path) -> None:
        """Test that valid JSON arrays are still parsed correctly."""
        self._insert_task_with_blocked_by(
            test_db, "SPEC-102", '["SPEC-001", "SPEC-002"]'
        )

        task = get_task("SPEC-102", project_path="/test/project", db_path=test_db)
        assert task is not None
        assert task.blocked_by == ["SPEC-001", "SPEC-002"]

    def test_null_blocked_by(self, test_db: Path) -> None:
        """Test that NULL blocked_by produces an empty list."""
        self._insert_task_with_blocked_by(test_db, "SPEC-103", None)

        task = get_task("SPEC-103", project_path="/test/project", db_path=test_db)
        assert task is not None
        assert task.blocked_by == []

    def test_empty_string_blocked_by(self, test_db: Path) -> None:
        """Test that empty string blocked_by produces an empty list."""
        self._insert_task_with_blocked_by(test_db, "SPEC-104", "")

        task = get_task("SPEC-104", project_path="/test/project", db_path=test_db)
        assert task is not None
        assert task.blocked_by == []

    def test_empty_json_array_blocked_by(self, test_db: Path) -> None:
        """Test that empty JSON array produces an empty list."""
        self._insert_task_with_blocked_by(test_db, "SPEC-105", "[]")

        task = get_task("SPEC-105", project_path="/test/project", db_path=test_db)
        assert task is not None
        assert task.blocked_by == []


class TestGetNextTaskId:
    """Tests for get_next_task_id function."""

    def test_next_id_empty_db(self, test_db: Path) -> None:
        """Test next ID when no tasks exist returns 001."""
        result = get_next_task_id("BUG", db_path=test_db)
        assert result == "BUG-001"

    def test_next_id_with_existing_tasks(self, test_db: Path) -> None:
        """Test next ID increments from highest existing."""
        create_task(
            task_id="BUG-001",
            title="Bug 1",
            task_type="bug",
            project_path="/test/project",
            db_path=test_db,
        )
        create_task(
            task_id="BUG-005",
            title="Bug 5",
            task_type="bug",
            project_path="/test/project",
            db_path=test_db,
        )

        result = get_next_task_id("BUG", db_path=test_db)
        assert result == "BUG-006"

    def test_next_id_ignores_subtasks(self, test_db: Path) -> None:
        """Test that subtask IDs like SPEC-001-01 are ignored."""
        create_task(
            task_id="SPEC-003",
            title="Spec 3",
            project_path="/test/project",
            db_path=test_db,
        )
        create_task(
            task_id="SPEC-003-01",
            title="Subtask",
            spec_id="SPEC-003",
            project_path="/test/project",
            db_path=test_db,
        )

        result = get_next_task_id("SPEC", db_path=test_db)
        assert result == "SPEC-004"

    def test_next_id_different_prefixes(self, test_db: Path) -> None:
        """Test that different prefixes are independent."""
        create_task(
            task_id="BUG-010",
            title="Bug",
            task_type="bug",
            project_path="/test/project",
            db_path=test_db,
        )
        create_task(
            task_id="SPEC-002",
            title="Spec",
            project_path="/test/project",
            db_path=test_db,
        )

        assert get_next_task_id("BUG", db_path=test_db) == "BUG-011"
        assert get_next_task_id("SPEC", db_path=test_db) == "SPEC-003"

