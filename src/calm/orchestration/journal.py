"""Session journal operations for CALM.

This module handles storing, listing, and managing session journal entries.
These are distinct from orchestration session handoffs - journal entries
capture session summaries, friction points, and session logs for the
learning reflection loop.
"""

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from calm.config import settings
from calm.db.connection import get_connection


@dataclass
class JournalEntry:
    """Represents a session journal entry."""

    id: str
    created_at: datetime
    working_directory: str
    project_name: str | None
    session_log_path: str | None
    summary: str
    friction_points: list[str]
    next_steps: list[str]
    reflected_at: datetime | None
    memories_created: int
    session_log: str | None = field(default=None)


def store_journal_entry(
    summary: str,
    working_directory: str,
    friction_points: list[str] | None = None,
    next_steps: list[str] | None = None,
    session_log_content: str | None = None,
    db_path: Path | None = None,
) -> tuple[str, str | None]:
    """Store a new session journal entry.

    Args:
        summary: Session summary text
        working_directory: The working directory of the session
        friction_points: List of friction points encountered
        next_steps: Recommended next steps
        session_log_content: Raw session log content to store
        db_path: Optional path to database file

    Returns:
        Tuple of (entry_id, session_log_path or None)
    """
    entry_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    project_name = Path(working_directory).name
    session_log_path: str | None = None

    # Save session log if provided
    if session_log_content:
        sessions_dir = settings.sessions_dir
        sessions_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        log_filename = f"{timestamp}_{entry_id}.jsonl"
        log_path = sessions_dir / log_filename
        log_path.write_text(session_log_content)
        session_log_path = str(log_path)

    # Store in database
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO session_journal
            (id, created_at, working_directory, project_name, session_log_path,
             summary, friction_points, next_steps)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                now,
                working_directory,
                project_name,
                session_log_path,
                summary,
                json.dumps(friction_points or []),
                json.dumps(next_steps or []),
            ),
        )
        conn.commit()

    return entry_id, session_log_path


def list_journal_entries(
    unreflected_only: bool = False,
    project_name: str | None = None,
    working_directory: str | None = None,
    limit: int = 50,
    db_path: Path | None = None,
) -> list[JournalEntry]:
    """List session journal entries with optional filters.

    Args:
        unreflected_only: Only return entries where reflected_at is NULL
        project_name: Filter by project name
        working_directory: Filter by exact working directory
        limit: Maximum entries to return
        db_path: Optional path to database file

    Returns:
        List of JournalEntry objects
    """
    query = "SELECT * FROM session_journal WHERE 1=1"
    params: list[Any] = []

    if unreflected_only:
        query += " AND reflected_at IS NULL"
    if project_name:
        query += " AND project_name = ?"
        params.append(project_name)
    if working_directory:
        query += " AND working_directory = ?"
        params.append(working_directory)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [_row_to_entry(row) for row in cursor.fetchall()]


def get_journal_entry(
    entry_id: str,
    include_log: bool = False,
    db_path: Path | None = None,
) -> JournalEntry | None:
    """Get a journal entry by ID.

    Args:
        entry_id: The entry ID
        include_log: Include the full session log content
        db_path: Optional path to database file

    Returns:
        JournalEntry or None if not found
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM session_journal WHERE id = ?", (entry_id,))
        row = cursor.fetchone()
        if not row:
            return None

        entry = _row_to_entry(row)

        if include_log and entry.session_log_path:
            log_path = Path(entry.session_log_path)
            if log_path.exists():
                entry.session_log = log_path.read_text()

        return entry


def mark_entries_reflected(
    entry_ids: list[str],
    memories_created: int | None = None,
    delete_logs: bool = True,
    db_path: Path | None = None,
) -> tuple[int, int]:
    """Mark entries as reflected.

    Args:
        entry_ids: List of entry IDs to mark
        memories_created: Number of memories created from this batch
        delete_logs: Delete session log files after marking
        db_path: Optional path to database file

    Returns:
        Tuple of (marked_count, logs_deleted)
    """
    now = datetime.now(UTC).isoformat()
    marked_count = 0
    logs_deleted = 0

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        for entry_id in entry_ids:
            # Get current entry for log path
            cursor.execute(
                "SELECT session_log_path FROM session_journal WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            if not row:
                continue

            # Update entry
            if memories_created is not None:
                cursor.execute(
                    """
                    UPDATE session_journal
                    SET reflected_at = ?, memories_created = ?
                    WHERE id = ?
                    """,
                    (now, memories_created, entry_id),
                )
            else:
                cursor.execute(
                    "UPDATE session_journal SET reflected_at = ? WHERE id = ?",
                    (now, entry_id),
                )

            if cursor.rowcount > 0:
                marked_count += 1

            # Delete log file if requested
            if delete_logs and row["session_log_path"]:
                log_path = Path(row["session_log_path"])
                if log_path.exists():
                    log_path.unlink()
                    logs_deleted += 1

        conn.commit()

    return marked_count, logs_deleted


def _row_to_entry(row: sqlite3.Row) -> JournalEntry:
    """Convert database row to JournalEntry."""
    return JournalEntry(
        id=row["id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        working_directory=row["working_directory"],
        project_name=row["project_name"],
        session_log_path=row["session_log_path"],
        summary=row["summary"],
        friction_points=json.loads(row["friction_points"] or "[]"),
        next_steps=json.loads(row["next_steps"] or "[]"),
        reflected_at=(
            datetime.fromisoformat(row["reflected_at"])
            if row["reflected_at"]
            else None
        ),
        memories_created=row["memories_created"] or 0,
    )
