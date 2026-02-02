"""Tests for CALM orchestration tasks module."""

from pathlib import Path

import pytest

from calm.db.schema import init_database
from calm.orchestration.tasks import (
    create_task,
    delete_task,
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
