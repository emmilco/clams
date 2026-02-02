"""Counter management for CALM orchestration.

Counters are used for tracking batch job triggers (e.g., E2E tests, docs).
"""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from calm.config import settings


@contextmanager
def _get_connection(
    db_path: Path | None = None,
) -> Generator[sqlite3.Connection, None, None]:
    """Get a database connection with proper cleanup.

    Args:
        db_path: Path to database file. Defaults to settings.db_path.

    Yields:
        SQLite connection with foreign keys enabled
    """
    if db_path is None:
        db_path = settings.db_path

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
    finally:
        conn.close()


def list_counters(db_path: Path | None = None) -> dict[str, int]:
    """List all counters with their values.

    Args:
        db_path: Optional path to database file

    Returns:
        Dict mapping counter names to values
    """
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, value FROM counters ORDER BY name")
        return {row["name"]: row["value"] for row in cursor.fetchall()}


def get_counter(name: str, db_path: Path | None = None) -> int:
    """Get a counter value.

    Args:
        name: Counter name
        db_path: Optional path to database file

    Returns:
        The counter value, or 0 if not found
    """
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM counters WHERE name = ?", (name,))
        row = cursor.fetchone()
        return row["value"] if row else 0


def set_counter(name: str, value: int, db_path: Path | None = None) -> None:
    """Set a counter to a specific value.

    Args:
        name: Counter name
        value: New value
        db_path: Optional path to database file
    """
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE counters SET value = ? WHERE name = ?",
            (value, name),
        )
        if cursor.rowcount == 0:
            cursor.execute(
                "INSERT INTO counters (name, value) VALUES (?, ?)",
                (name, value),
            )
        conn.commit()


def increment_counter(name: str, db_path: Path | None = None) -> int:
    """Increment a counter by 1.

    Args:
        name: Counter name
        db_path: Optional path to database file

    Returns:
        The new counter value
    """
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE counters SET value = value + 1 WHERE name = ?",
            (name,),
        )
        if cursor.rowcount == 0:
            cursor.execute(
                "INSERT INTO counters (name, value) VALUES (?, 1)",
                (name,),
            )
            conn.commit()
            return 1
        conn.commit()

        cursor.execute("SELECT value FROM counters WHERE name = ?", (name,))
        row = cursor.fetchone()
        return row["value"] if row else 1


def reset_counter(name: str, db_path: Path | None = None) -> None:
    """Reset a counter to 0.

    Args:
        name: Counter name
        db_path: Optional path to database file
    """
    set_counter(name, 0, db_path)


def add_counter(
    name: str, initial_value: int = 0, db_path: Path | None = None
) -> None:
    """Create a new counter.

    Args:
        name: Counter name
        initial_value: Initial value (default 0)
        db_path: Optional path to database file
    """
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO counters (name, value) VALUES (?, ?)",
            (name, initial_value),
        )
        conn.commit()
