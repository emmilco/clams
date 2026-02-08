"""Task management for CALM orchestration.

This module provides CRUD operations and transitions for tasks.
"""

import json
import re
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from calm.config import settings
from calm.orchestration.phases import (
    get_initial_phase,
    get_transition_name,
    is_valid_transition,
)
from calm.orchestration.project import detect_main_repo


@dataclass
class Task:
    """Represents a task in the orchestration system."""

    id: str
    title: str
    spec_id: str | None
    task_type: str
    phase: str
    specialist: str | None
    notes: str | None
    blocked_by: list[str]
    worktree_path: str | None
    project_path: str
    created_at: datetime
    updated_at: datetime


@contextmanager
def _get_connection(
    db_path: Path | None = None,
) -> Generator[sqlite3.Connection, None, None]:
    """Get a database connection with proper cleanup."""
    if db_path is None:
        db_path = settings.db_path

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
    finally:
        conn.close()


def _row_to_task(row: sqlite3.Row) -> Task:
    """Convert a database row to a Task object."""
    blocked_by_str = row["blocked_by"]
    blocked_by: list[str] = []
    if blocked_by_str:
        try:
            blocked_by = json.loads(blocked_by_str)
        except json.JSONDecodeError:
            # Handle malformed data: bare task ID strings stored without JSON serialization
            blocked_by = [s.strip() for s in blocked_by_str.split(",") if s.strip()]

    return Task(
        id=row["id"],
        title=row["title"],
        spec_id=row["spec_id"],
        task_type=row["task_type"],
        phase=row["phase"],
        specialist=row["specialist"],
        notes=row["notes"],
        blocked_by=blocked_by,
        worktree_path=row["worktree_path"],
        project_path=row["project_path"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def create_task(
    task_id: str,
    title: str,
    task_type: str = "feature",
    spec_id: str | None = None,
    project_path: str | None = None,
    db_path: Path | None = None,
) -> Task:
    """Create a new task in the database.

    Args:
        task_id: Unique task identifier (e.g., "SPEC-001" or "BUG-001")
        title: Task title
        task_type: Either 'feature' or 'bug'
        spec_id: Parent spec ID for subtasks
        project_path: Project path (auto-detected if not provided)
        db_path: Optional path to database file

    Returns:
        The created Task

    Raises:
        ValueError: If task_id already exists or task_type is invalid
    """
    if project_path is None:
        project_path = detect_main_repo()

    initial_phase = get_initial_phase(task_type)
    now = datetime.now().isoformat()

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO tasks (
                    id, title, spec_id, task_type, phase,
                    project_path, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    title,
                    spec_id,
                    task_type,
                    initial_phase,
                    project_path,
                    now,
                    now,
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Task {task_id} already exists") from e

        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return _row_to_task(row)


def get_task(
    task_id: str,
    project_path: str | None = None,
    db_path: Path | None = None,
) -> Task | None:
    """Get a task by ID.

    Args:
        task_id: Task identifier
        project_path: Project path filter (auto-detected if not provided)
        db_path: Optional path to database file

    Returns:
        The Task or None if not found
    """
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()

        # If project_path is provided, filter by it
        if project_path is not None:
            cursor.execute(
                "SELECT * FROM tasks WHERE id = ? AND project_path = ?",
                (task_id, project_path),
            )
        else:
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))

        row = cursor.fetchone()
        return _row_to_task(row) if row else None


def list_tasks(
    phase: str | None = None,
    task_type: str | None = None,
    project_path: str | None = None,
    include_done: bool = False,
    db_path: Path | None = None,
) -> list[Task]:
    """List tasks with optional filtering.

    Args:
        phase: Filter by phase
        task_type: Filter by task type ('feature' or 'bug')
        project_path: Project path filter (auto-detected if not provided)
        include_done: Include tasks in DONE phase
        db_path: Optional path to database file

    Returns:
        List of tasks matching the filters
    """
    if project_path is None:
        project_path = detect_main_repo()

    query = "SELECT * FROM tasks WHERE project_path = ?"
    params: list[str] = [project_path]

    if phase is not None:
        query += " AND phase = ?"
        params.append(phase)

    if task_type is not None:
        query += " AND task_type = ?"
        params.append(task_type)

    if not include_done:
        query += " AND phase != 'DONE'"

    query += " ORDER BY created_at DESC"

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [_row_to_task(row) for row in cursor.fetchall()]


def update_task(
    task_id: str,
    phase: str | None = None,
    specialist: str | None = None,
    notes: str | None = None,
    blocked_by: list[str] | None = None,
    worktree_path: str | None = None,
    db_path: Path | None = None,
) -> Task:
    """Update task fields.

    Args:
        task_id: Task identifier
        phase: New phase (for direct phase updates, use transition_task)
        specialist: New specialist assignment
        notes: New notes
        blocked_by: New blocked_by list
        worktree_path: New worktree path
        db_path: Optional path to database file

    Returns:
        The updated Task

    Raises:
        ValueError: If task not found
    """
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Get current task
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Task {task_id} not found")

        # Build update query
        updates: list[str] = []
        params: list[str | None] = []

        if phase is not None:
            updates.append("phase = ?")
            params.append(phase)

        if specialist is not None:
            updates.append("specialist = ?")
            params.append(specialist)

        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)

        if blocked_by is not None:
            updates.append("blocked_by = ?")
            params.append(json.dumps(blocked_by))

        if worktree_path is not None:
            updates.append("worktree_path = ?")
            params.append(worktree_path)

        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            params.append(task_id)

            query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()

        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return _row_to_task(row)


def transition_task(
    task_id: str,
    to_phase: str,
    gate_result: str | None = None,
    gate_details: str | None = None,
    db_path: Path | None = None,
) -> Task:
    """Transition task to a new phase with validation.

    Args:
        task_id: Task identifier
        to_phase: Target phase
        gate_result: Gate result ('pass' or 'fail')
        gate_details: Gate details/notes
        db_path: Optional path to database file

    Returns:
        The updated Task

    Raises:
        ValueError: If task not found or transition is invalid
    """
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Get current task
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Task {task_id} not found")

        from_phase = row["phase"]
        task_type = row["task_type"]

        # Validate transition
        if not is_valid_transition(task_type, from_phase, to_phase):
            raise ValueError(
                f"Invalid transition: {from_phase} -> {to_phase} for {task_type}"
            )

        now = datetime.now().isoformat()

        # Record the transition
        cursor.execute(
            """
            INSERT INTO phase_transitions
            (task_id, from_phase, to_phase, gate_result, gate_details, transitioned_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (task_id, from_phase, to_phase, gate_result, gate_details, now),
        )

        # Update the task
        cursor.execute(
            "UPDATE tasks SET phase = ?, updated_at = ? WHERE id = ?",
            (to_phase, now, task_id),
        )

        conn.commit()

        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return _row_to_task(row)


def delete_task(
    task_id: str,
    db_path: Path | None = None,
) -> None:
    """Delete a task and related records.

    Args:
        task_id: Task identifier
        db_path: Optional path to database file

    Raises:
        ValueError: If task not found
    """
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Check if task exists
        cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
        if not cursor.fetchone():
            raise ValueError(f"Task {task_id} not found")

        # Delete related records first (due to foreign keys)
        cursor.execute("DELETE FROM reviews WHERE task_id = ?", (task_id,))
        cursor.execute("DELETE FROM test_runs WHERE task_id = ?", (task_id,))
        cursor.execute("DELETE FROM phase_transitions WHERE task_id = ?", (task_id,))
        cursor.execute("DELETE FROM gate_passes WHERE task_id = ?", (task_id,))
        cursor.execute("DELETE FROM workers WHERE task_id = ?", (task_id,))

        # Delete the task
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()


def get_next_task_id(
    prefix: str,
    db_path: Path | None = None,
) -> str:
    """Get the next available task ID for a given prefix.

    Queries the database for the highest numeric suffix with the given
    prefix (e.g., "BUG" or "SPEC") and returns the next sequential ID.

    Args:
        prefix: Task ID prefix ("BUG" or "SPEC")
        db_path: Optional path to database file

    Returns:
        The next available task ID (e.g., "BUG-072" or "SPEC-059")
    """
    pattern = f"{prefix}-%"

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM tasks WHERE id LIKE ?",
            (pattern,),
        )
        rows = cursor.fetchall()

    max_num = 0
    # Match IDs like PREFIX-NNN (not subtasks like PREFIX-NNN-NN)
    id_pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    for row in rows:
        match = id_pattern.match(row["id"])
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num

    next_num = max_num + 1
    return f"{prefix}-{next_num:03d}"


def get_transition_name_for_task(task_id: str, db_path: Path | None = None) -> str:
    """Get the next transition name for a task.

    Args:
        task_id: Task identifier
        db_path: Optional path to database file

    Returns:
        Transition name in format "FROM-TO"

    Raises:
        ValueError: If task not found or no valid transitions
    """
    task = get_task(task_id, db_path=db_path)
    if not task:
        raise ValueError(f"Task {task_id} not found")

    from calm.orchestration.phases import get_next_phases

    next_phases = get_next_phases(task.task_type, task.phase)
    if not next_phases:
        raise ValueError(f"No valid transitions from {task.phase}")

    return get_transition_name(task.phase, next_phases[0])
