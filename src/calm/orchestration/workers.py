"""Worker management for CALM orchestration.

This module handles worker registration, status tracking, and context generation.
"""

import random
import sqlite3
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from calm.config import settings
from calm.orchestration.project import detect_project_path

WorkerStatus = Literal["active", "completed", "failed", "session_ended"]


@dataclass
class Worker:
    """Represents a worker in the orchestration system."""

    id: str
    task_id: str
    role: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    project_path: str | None


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


def _row_to_worker(row: sqlite3.Row) -> Worker:
    """Convert a database row to a Worker object."""
    return Worker(
        id=row["id"],
        task_id=row["task_id"],
        role=row["role"],
        status=row["status"],
        started_at=datetime.fromisoformat(row["started_at"]),
        ended_at=(
            datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None
        ),
        project_path=row["project_path"],
    )


def _generate_worker_id() -> str:
    """Generate a unique worker ID."""
    timestamp = int(time.time())
    random_suffix = random.randint(10000, 99999)
    return f"W-{timestamp}-{random_suffix}"


def start_worker(
    task_id: str,
    role: str,
    project_path: str | None = None,
    db_path: Path | None = None,
) -> str:
    """Register a worker and return its ID.

    Args:
        task_id: Task the worker is assigned to
        role: Worker role (e.g., 'backend', 'reviewer')
        project_path: Project path (auto-detected if not provided)
        db_path: Optional path to database file

    Returns:
        The generated worker ID
    """
    if project_path is None:
        project_path = detect_project_path()

    worker_id = _generate_worker_id()
    now = datetime.now().isoformat()

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO workers (id, task_id, role, status, started_at, project_path)
            VALUES (?, ?, ?, 'active', ?, ?)
            """,
            (worker_id, task_id, role, now, project_path),
        )
        conn.commit()

    return worker_id


def complete_worker(
    worker_id: str,
    db_path: Path | None = None,
) -> None:
    """Mark a worker as completed.

    Args:
        worker_id: Worker ID
        db_path: Optional path to database file

    Raises:
        ValueError: If worker not found
    """
    now = datetime.now().isoformat()

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE workers SET status = 'completed', ended_at = ? WHERE id = ?",
            (now, worker_id),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Worker {worker_id} not found")
        conn.commit()


def fail_worker(
    worker_id: str,
    reason: str | None = None,
    db_path: Path | None = None,
) -> None:
    """Mark a worker as failed.

    Args:
        worker_id: Worker ID
        reason: Optional failure reason (currently not stored, for logging)
        db_path: Optional path to database file

    Raises:
        ValueError: If worker not found
    """
    now = datetime.now().isoformat()

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE workers SET status = 'failed', ended_at = ? WHERE id = ?",
            (now, worker_id),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Worker {worker_id} not found")
        conn.commit()


def list_workers(
    status: str | None = None,
    project_path: str | None = None,
    db_path: Path | None = None,
) -> list[Worker]:
    """List workers with optional filtering.

    Args:
        status: Filter by status
        project_path: Project path filter (auto-detected if not provided)
        db_path: Optional path to database file

    Returns:
        List of workers
    """
    if project_path is None:
        project_path = detect_project_path()

    query = "SELECT * FROM workers WHERE project_path = ?"
    params: list[str] = [project_path]

    if status is not None:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY started_at DESC"

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [_row_to_worker(row) for row in cursor.fetchall()]


def cleanup_stale_workers(
    max_age_hours: int = 2,
    db_path: Path | None = None,
) -> int:
    """Mark workers active for too long as session_ended.

    Args:
        max_age_hours: Maximum age in hours before marking stale
        db_path: Optional path to database file

    Returns:
        Number of workers marked as stale
    """
    cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
    now = datetime.now().isoformat()

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE workers
            SET status = 'session_ended', ended_at = ?
            WHERE status = 'active' AND started_at < ?
            """,
            (now, cutoff),
        )
        count = cursor.rowcount
        conn.commit()
        return count


def get_role_prompt(
    role: str,
    roles_dir: Path | None = None,
) -> str:
    """Get the role prompt markdown for a given role.

    Looks for role files in:
    1. ~/.calm/roles/<role>.md
    2. .claude/roles/<role>.md (fallback)

    Args:
        role: Role name (e.g., 'backend', 'reviewer')
        roles_dir: Optional override for roles directory

    Returns:
        The role prompt content

    Raises:
        FileNotFoundError: If role file not found
    """
    if roles_dir is None:
        roles_dir = settings.roles_dir

    # Try primary location
    role_file = roles_dir / f"{role}.md"
    if role_file.exists():
        return role_file.read_text()

    # Fallback to .claude/roles
    fallback_dir = Path.cwd() / ".claude" / "roles"
    fallback_file = fallback_dir / f"{role}.md"
    if fallback_file.exists():
        return fallback_file.read_text()

    raise FileNotFoundError(f"Role file not found: {role}.md")


def get_worker_context(
    task_id: str,
    role: str,
    roles_dir: Path | None = None,
    db_path: Path | None = None,
) -> str:
    """Generate full context for a worker including role prompt and task info.

    Args:
        task_id: Task identifier
        role: Worker role
        roles_dir: Optional override for roles directory
        db_path: Optional path to database file

    Returns:
        Full context markdown for the worker
    """
    from calm.orchestration.tasks import get_task

    # Get role prompt
    try:
        role_prompt = get_role_prompt(role, roles_dir)
    except FileNotFoundError:
        role_prompt = f"# {role.title()} Role\n\nNo role prompt found for {role}."

    # Get task info
    task = get_task(task_id, db_path=db_path)
    if not task:
        task_info = f"Task {task_id} not found."
    else:
        task_info = f"""## Task Information

- **ID**: {task.id}
- **Title**: {task.title}
- **Type**: {task.task_type}
- **Phase**: {task.phase}
- **Spec ID**: {task.spec_id or "N/A"}
- **Worktree**: {task.worktree_path or "N/A"}
"""

    # Build context
    context = f"""# Worker Context for {task_id}

## Role: {role}

{role_prompt}

---

{task_info}
"""

    return context
