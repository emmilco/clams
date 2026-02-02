"""Review management for CALM orchestration.

This module handles review recording, checking, and clearing.
"""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from calm.config import settings

ReviewType = Literal["spec", "proposal", "code", "bugfix"]
ReviewResult = Literal["approved", "changes_requested"]


@dataclass
class Review:
    """Represents a review in the orchestration system."""

    id: int
    task_id: str
    review_type: str
    result: str
    worker_id: str | None
    reviewer_notes: str | None
    created_at: datetime


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


def _row_to_review(row: sqlite3.Row) -> Review:
    """Convert a database row to a Review object."""
    return Review(
        id=row["id"],
        task_id=row["task_id"],
        review_type=row["review_type"],
        result=row["result"],
        worker_id=row["worker_id"],
        reviewer_notes=row["reviewer_notes"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def record_review(
    task_id: str,
    review_type: str,
    result: str,
    worker_id: str | None = None,
    notes: str | None = None,
    db_path: Path | None = None,
) -> Review:
    """Record a review result.

    If changes_requested, clears previous reviews for that artifact
    to restart the review cycle.

    Args:
        task_id: Task identifier
        review_type: Type of review ('spec', 'proposal', 'code', 'bugfix')
        result: Review result ('approved', 'changes_requested')
        worker_id: Optional worker ID who performed the review
        notes: Optional reviewer notes
        db_path: Optional path to database file

    Returns:
        The recorded Review

    Raises:
        ValueError: If review_type or result is invalid
    """
    valid_types = {"spec", "proposal", "code", "bugfix"}
    valid_results = {"approved", "changes_requested"}

    if review_type not in valid_types:
        raise ValueError(f"Invalid review type: {review_type}")
    if result not in valid_results:
        raise ValueError(f"Invalid result: {result}")

    now = datetime.now().isoformat()

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()

        # If changes requested, clear previous reviews to restart cycle
        if result == "changes_requested":
            cursor.execute(
                "DELETE FROM reviews WHERE task_id = ? AND review_type = ?",
                (task_id, review_type),
            )

        cursor.execute(
            """
            INSERT INTO reviews (
                task_id, review_type, result, worker_id, reviewer_notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (task_id, review_type, result, worker_id, notes, now),
        )
        conn.commit()

        review_id = cursor.lastrowid
        cursor.execute("SELECT * FROM reviews WHERE id = ?", (review_id,))
        row = cursor.fetchone()
        return _row_to_review(row)


def list_reviews(
    task_id: str,
    review_type: str | None = None,
    db_path: Path | None = None,
) -> list[Review]:
    """List reviews for a task.

    Args:
        task_id: Task identifier
        review_type: Optional type filter
        db_path: Optional path to database file

    Returns:
        List of reviews
    """
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()

        if review_type is not None:
            cursor.execute(
                """
                SELECT * FROM reviews
                WHERE task_id = ? AND review_type = ?
                ORDER BY created_at DESC
                """,
                (task_id, review_type),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM reviews
                WHERE task_id = ?
                ORDER BY created_at DESC
                """,
                (task_id,),
            )

        return [_row_to_review(row) for row in cursor.fetchall()]


def check_reviews(
    task_id: str,
    review_type: str,
    required: int = 2,
    db_path: Path | None = None,
) -> tuple[bool, int]:
    """Check if review requirements are met.

    Args:
        task_id: Task identifier
        review_type: Type of review to check
        required: Number of required approvals (default 2)
        db_path: Optional path to database file

    Returns:
        Tuple of (passed, count) where passed is True if requirements met
    """
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*) as count FROM reviews
            WHERE task_id = ? AND review_type = ? AND result = 'approved'
            """,
            (task_id, review_type),
        )
        row = cursor.fetchone()
        count = row["count"] if row else 0
        return count >= required, count


def clear_reviews(
    task_id: str,
    review_type: str | None = None,
    db_path: Path | None = None,
) -> int:
    """Clear reviews for a task.

    Args:
        task_id: Task identifier
        review_type: Optional type filter (clears all if not provided)
        db_path: Optional path to database file

    Returns:
        Number of reviews cleared
    """
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()

        if review_type is not None:
            cursor.execute(
                "DELETE FROM reviews WHERE task_id = ? AND review_type = ?",
                (task_id, review_type),
            )
        else:
            cursor.execute("DELETE FROM reviews WHERE task_id = ?", (task_id,))

        count = cursor.rowcount
        conn.commit()
        return count
