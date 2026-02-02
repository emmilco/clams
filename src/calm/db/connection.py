"""Database connection management for CALM."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from calm.config import settings


@contextmanager
def get_connection(
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
    conn.row_factory = sqlite3.Row  # Enable dict-like access
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
    finally:
        conn.close()
