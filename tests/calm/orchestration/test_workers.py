"""Tests for CALM orchestration workers module."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from calm.db.schema import init_database
from calm.orchestration.tasks import create_task
from calm.orchestration.workers import (
    cleanup_stale_workers,
    complete_worker,
    fail_worker,
    list_workers,
    start_worker,
)


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Create a temporary test database."""
    db_path = tmp_path / "test.db"
    init_database(db_path)
    return db_path


@pytest.fixture
def task_with_db(test_db: Path) -> tuple[str, Path]:
    """Create a task and return (task_id, db_path)."""
    create_task(
        task_id="SPEC-001",
        title="Test Task",
        project_path="/test/project",
        db_path=test_db,
    )
    return "SPEC-001", test_db


class TestStartWorker:
    """Tests for start_worker function."""

    def test_start_worker(self, task_with_db: tuple[str, Path]) -> None:
        """Test starting a worker."""
        task_id, db_path = task_with_db

        worker_id = start_worker(
            task_id=task_id,
            role="backend",
            project_path="/test/project",
            db_path=db_path,
        )

        assert worker_id.startswith("W-")
        assert len(worker_id) > 5

    def test_start_worker_appears_in_list(
        self, task_with_db: tuple[str, Path]
    ) -> None:
        """Test that started worker appears in list."""
        task_id, db_path = task_with_db

        worker_id = start_worker(
            task_id=task_id,
            role="backend",
            project_path="/test/project",
            db_path=db_path,
        )

        workers = list_workers(project_path="/test/project", db_path=db_path)
        assert len(workers) == 1
        assert workers[0].id == worker_id
        assert workers[0].status == "active"


class TestCompleteWorker:
    """Tests for complete_worker function."""

    def test_complete_worker(self, task_with_db: tuple[str, Path]) -> None:
        """Test completing a worker."""
        task_id, db_path = task_with_db

        worker_id = start_worker(
            task_id=task_id,
            role="backend",
            project_path="/test/project",
            db_path=db_path,
        )

        complete_worker(worker_id, db_path=db_path)

        workers = list_workers(
            status="completed", project_path="/test/project", db_path=db_path
        )
        assert len(workers) == 1
        assert workers[0].id == worker_id
        assert workers[0].ended_at is not None

    def test_complete_nonexistent_raises(self, test_db: Path) -> None:
        """Test completing nonexistent worker raises error."""
        with pytest.raises(ValueError, match="not found"):
            complete_worker("W-nonexistent", db_path=test_db)


class TestFailWorker:
    """Tests for fail_worker function."""

    def test_fail_worker(self, task_with_db: tuple[str, Path]) -> None:
        """Test failing a worker."""
        task_id, db_path = task_with_db

        worker_id = start_worker(
            task_id=task_id,
            role="backend",
            project_path="/test/project",
            db_path=db_path,
        )

        fail_worker(worker_id, reason="Test failure", db_path=db_path)

        workers = list_workers(
            status="failed", project_path="/test/project", db_path=db_path
        )
        assert len(workers) == 1
        assert workers[0].id == worker_id

    def test_fail_nonexistent_raises(self, test_db: Path) -> None:
        """Test failing nonexistent worker raises error."""
        with pytest.raises(ValueError, match="not found"):
            fail_worker("W-nonexistent", db_path=test_db)


class TestListWorkers:
    """Tests for list_workers function."""

    def test_list_workers_empty(self, test_db: Path) -> None:
        """Test listing workers when none exist."""
        workers = list_workers(project_path="/test/project", db_path=test_db)
        assert workers == []

    def test_list_workers_by_status(
        self, task_with_db: tuple[str, Path]
    ) -> None:
        """Test filtering workers by status."""
        task_id, db_path = task_with_db

        # Start two workers
        worker1 = start_worker(
            task_id=task_id,
            role="backend",
            project_path="/test/project",
            db_path=db_path,
        )
        worker2 = start_worker(
            task_id=task_id,
            role="reviewer",
            project_path="/test/project",
            db_path=db_path,
        )

        # Complete one
        complete_worker(worker1, db_path=db_path)

        # List active workers
        active = list_workers(
            status="active", project_path="/test/project", db_path=db_path
        )
        assert len(active) == 1
        assert active[0].id == worker2

        # List completed workers
        completed = list_workers(
            status="completed", project_path="/test/project", db_path=db_path
        )
        assert len(completed) == 1
        assert completed[0].id == worker1


class TestCleanupStaleWorkers:
    """Tests for cleanup_stale_workers function."""

    def test_cleanup_stale_workers(
        self, task_with_db: tuple[str, Path]
    ) -> None:
        """Test cleaning up stale workers."""
        task_id, db_path = task_with_db

        # Start a worker
        start_worker(
            task_id=task_id,
            role="backend",
            project_path="/test/project",
            db_path=db_path,
        )

        # Mark it as stale by updating started_at to old time
        import sqlite3

        conn = sqlite3.connect(db_path)
        old_time = (datetime.now() - timedelta(hours=3)).isoformat()
        conn.execute(
            "UPDATE workers SET started_at = ? WHERE status = 'active'",
            (old_time,),
        )
        conn.commit()
        conn.close()

        # Cleanup
        count = cleanup_stale_workers(max_age_hours=2, db_path=db_path)
        assert count == 1

        # Verify worker is now session_ended
        workers = list_workers(
            status="session_ended", project_path="/test/project", db_path=db_path
        )
        assert len(workers) == 1
