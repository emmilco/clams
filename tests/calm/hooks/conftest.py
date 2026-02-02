"""Test fixtures for CALM hooks tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from calm.db.schema import init_database

if TYPE_CHECKING:
    pass


@pytest.fixture
def temp_calm_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create temporary CALM home with tool_count file support."""
    calm_home = tmp_path / ".calm"
    calm_home.mkdir()

    # Patch settings to use temp directory
    monkeypatch.setenv("CALM_HOME", str(calm_home))
    monkeypatch.setenv("CALM_DB_PATH", str(calm_home / "metadata.db"))

    return calm_home


@pytest.fixture
def temp_db(temp_calm_home: Path) -> Path:
    """Create temporary database with schema."""
    db_path = temp_calm_home / "metadata.db"
    init_database(db_path)
    return db_path


@pytest.fixture
def db_with_tasks(temp_db: Path) -> Path:
    """Database with sample tasks."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO tasks (id, title, task_type, phase, project_path, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "SPEC-001",
            "Test Task",
            "feature",
            "IMPLEMENT",
            "/test/project",
            "2026-01-01T00:00:00",
            "2026-01-01T00:00:00",
        ),
    )
    cursor.execute(
        """
        INSERT INTO tasks (id, title, task_type, phase, project_path, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "BUG-001",
            "Test Bug",
            "bug",
            "FIXED",
            "/test/project",
            "2026-01-01T00:00:00",
            "2026-01-01T00:00:00",
        ),
    )
    conn.commit()
    conn.close()
    return temp_db


@pytest.fixture
def db_with_active_ghap(temp_db: Path) -> Path:
    """Database with active GHAP entry."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO ghap_entries
        (id, domain, strategy, goal, hypothesis, action, prediction, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "ghap-001",
            "debugging",
            "systematic-elimination",
            "Fix test failures",
            "Missing await on database call",
            "Add await to db.query()",
            "Tests will pass after adding await",
            "active",
            "2026-01-01T00:00:00",
        ),
    )
    conn.commit()
    conn.close()
    return temp_db


@pytest.fixture
def db_with_memories(temp_db: Path) -> Path:
    """Database with sample memories."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO memories
        (id, content, category, importance, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "mem-001",
            "When async tests hang, check for missing await on database calls",
            "error",
            0.8,
            "2026-01-01T00:00:00",
        ),
    )
    cursor.execute(
        """
        INSERT INTO memories
        (id, content, category, importance, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "mem-002",
            "MCP tools are registered via a dispatcher pattern",
            "fact",
            0.6,
            "2026-01-01T00:00:00",
        ),
    )
    conn.commit()
    conn.close()
    return temp_db


@pytest.fixture
def db_with_resolved_experiences(temp_db: Path) -> Path:
    """Database with resolved GHAP experiences."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO ghap_entries
        (id, domain, strategy, goal, hypothesis, action, prediction, status, resolved_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "ghap-resolved-001",
            "debugging",
            "systematic-elimination",
            "Fix async test failures",
            "Missing await on database call",
            "Add await to db.query()",
            "Tests will pass",
            "confirmed",
            "2026-01-02T00:00:00",
            "2026-01-01T00:00:00",
        ),
    )
    conn.commit()
    conn.close()
    return temp_db


@pytest.fixture
def tool_count_file(temp_calm_home: Path) -> Path:
    """Path to tool count file in temp CALM home."""
    return temp_calm_home / "tool_count"
