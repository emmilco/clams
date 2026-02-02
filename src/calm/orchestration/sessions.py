"""Session handoff management for CALM orchestration.

This module handles saving and retrieving session handoffs.
"""

import base64
import sqlite3
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from calm.config import settings


@dataclass
class Session:
    """Represents a session handoff in the orchestration system."""

    id: str
    created_at: datetime
    handoff_content: str
    needs_continuation: bool
    resumed_at: datetime | None


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


def _row_to_session(row: sqlite3.Row) -> Session:
    """Convert a database row to a Session object."""
    # Decode base64 content if present
    content = row["handoff_content"] or ""
    try:
        content = base64.b64decode(content).decode("utf-8")
    except Exception:
        pass  # Content may not be base64 encoded

    return Session(
        id=row["id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        handoff_content=content,
        needs_continuation=bool(row["needs_continuation"]),
        resumed_at=(
            datetime.fromisoformat(row["resumed_at"]) if row["resumed_at"] else None
        ),
    )


def save_session(
    content: str,
    needs_continuation: bool = False,
    db_path: Path | None = None,
) -> str:
    """Save session handoff.

    Args:
        content: Handoff markdown content
        needs_continuation: Whether session needs to be continued
        db_path: Optional path to database file

    Returns:
        The generated session ID
    """
    session_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()

    # Encode content as base64 for safe storage
    encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO sessions (id, created_at, handoff_content, needs_continuation)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, now, encoded_content, int(needs_continuation)),
        )
        conn.commit()

    return session_id


def list_sessions(
    limit: int = 10,
    db_path: Path | None = None,
) -> list[Session]:
    """List recent sessions.

    Args:
        limit: Maximum number of sessions to return
        db_path: Optional path to database file

    Returns:
        List of recent sessions
    """
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM sessions
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [_row_to_session(row) for row in cursor.fetchall()]


def get_session(
    session_id: str,
    db_path: Path | None = None,
) -> Session | None:
    """Get a session by ID.

    Args:
        session_id: Session identifier
        db_path: Optional path to database file

    Returns:
        The Session or None if not found
    """
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        return _row_to_session(row) if row else None


def get_pending_handoff(
    db_path: Path | None = None,
) -> Session | None:
    """Get the pending handoff (needs_continuation and not resumed).

    Args:
        db_path: Optional path to database file

    Returns:
        The pending Session or None if none found
    """
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM sessions
            WHERE needs_continuation = 1 AND resumed_at IS NULL
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        return _row_to_session(row) if row else None


def mark_session_resumed(
    session_id: str,
    db_path: Path | None = None,
) -> None:
    """Mark a session as resumed.

    Args:
        session_id: Session identifier
        db_path: Optional path to database file

    Raises:
        ValueError: If session not found
    """
    now = datetime.now().isoformat()

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sessions SET resumed_at = ? WHERE id = ?",
            (now, session_id),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Session {session_id} not found")
        conn.commit()


def generate_next_commands(
    db_path: Path | None = None,
) -> str:
    """Generate next commands markdown for active tasks.

    Args:
        db_path: Optional path to database file

    Returns:
        Markdown with next commands for each active task
    """
    from calm.orchestration.tasks import list_tasks

    tasks = list_tasks(include_done=False, db_path=db_path)

    if not tasks:
        return "No active tasks.\n"

    lines = ["## Next Commands\n"]

    for task in tasks:
        lines.append(f"### {task.id}: {task.title}")
        lines.append(f"- Phase: {task.phase}")
        lines.append(f"- Type: {task.task_type}")
        if task.worktree_path:
            lines.append(f"- Worktree: {task.worktree_path}")
        lines.append("")

    return "\n".join(lines)
