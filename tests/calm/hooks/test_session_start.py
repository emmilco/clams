"""Tests for SessionStart hook."""

from __future__ import annotations

import io
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from calm.hooks.session_start import (
    MAX_OUTPUT_CHARS,
    format_output,
    get_active_tasks,
    get_orphaned_ghap,
    main,
)


class TestGetOrphanedGhap:
    """Tests for get_orphaned_ghap function."""

    def test_no_active_ghap(self, temp_db: Path) -> None:
        """Test returns None when no active GHAP exists."""
        result = get_orphaned_ghap(temp_db)
        assert result is None

    def test_with_active_ghap(self, db_with_active_ghap: Path) -> None:
        """Test returns GHAP info when active GHAP exists."""
        result = get_orphaned_ghap(db_with_active_ghap)
        assert result is not None
        assert result["goal"] == "Fix test failures"
        assert result["hypothesis"] == "Missing await on database call"

    def test_missing_database(self, tmp_path: Path) -> None:
        """Test returns None when database doesn't exist."""
        result = get_orphaned_ghap(tmp_path / "nonexistent.db")
        assert result is None


class TestGetActiveTasks:
    """Tests for get_active_tasks function."""

    def test_no_tasks(self, temp_db: Path) -> None:
        """Test returns empty list when no tasks exist."""
        result = get_active_tasks(temp_db, "/test/project")
        assert result == []

    def test_with_tasks(self, db_with_tasks: Path) -> None:
        """Test returns tasks for matching project."""
        result = get_active_tasks(db_with_tasks, "/test/project")
        assert len(result) == 2
        task_ids = [t[0] for t in result]
        assert "SPEC-001" in task_ids
        assert "BUG-001" in task_ids

    def test_wrong_project(self, db_with_tasks: Path) -> None:
        """Test returns empty list for different project."""
        result = get_active_tasks(db_with_tasks, "/different/project")
        assert result == []

    def test_excludes_done_tasks(self, temp_db: Path) -> None:
        """Test excludes tasks in DONE phase."""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tasks (id, title, task_type, phase, project_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "SPEC-DONE",
                "Done Task",
                "feature",
                "DONE",
                "/test/project",
                "2026-01-01T00:00:00",
                "2026-01-01T00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        result = get_active_tasks(temp_db, "/test/project")
        task_ids = [t[0] for t in result]
        assert "SPEC-DONE" not in task_ids

    def test_missing_database(self, tmp_path: Path) -> None:
        """Test returns empty list when database doesn't exist."""
        result = get_active_tasks(tmp_path / "nonexistent.db", "/test/project")
        assert result == []


class TestFormatOutput:
    """Tests for format_output function."""

    def test_no_tasks_no_orphan_server_available(self) -> None:
        """Test output with no tasks, no orphan, server available."""
        output = format_output(orphan=None, tasks=[], server_available=True)
        assert "CALM (Claude Agent Learning & Management) is available." in output
        assert "Always active: /wrapup, /reflection, memory tools" in output
        assert "/orchestrate" in output
        assert "explicitly ask the user" in output

    def test_no_tasks_server_starting(self) -> None:
        """Test output when server is starting."""
        output = format_output(orphan=None, tasks=[], server_available=False)
        assert "CALM available (server starting...)" in output

    def test_with_tasks(self) -> None:
        """Test output with tasks."""
        tasks = [("SPEC-001", "IMPLEMENT"), ("BUG-002", "FIXED")]
        output = format_output(orphan=None, tasks=tasks, server_available=True)
        assert "2 active task(s)" in output
        assert "SPEC-001 IMPLEMENT" in output
        assert "BUG-002 FIXED" in output

    def test_with_orphan(self) -> None:
        """Test output with orphaned GHAP."""
        orphan = {"goal": "Fix the bug", "hypothesis": "Bad config"}
        output = format_output(orphan=orphan, tasks=[], server_available=True)
        assert "[GHAP Warning]" in output
        assert "Fix the bug" in output
        assert "Bad config" in output

    def test_long_orphan_truncated(self) -> None:
        """Test long GHAP fields are truncated."""
        orphan = {"goal": "x" * 200, "hypothesis": "y" * 200}
        output = format_output(orphan=orphan, tasks=[], server_available=True)
        # Check truncation happens (80 chars + "...")
        assert "x" * 80 in output
        assert "x" * 100 not in output


class TestMain:
    """Tests for main entry point."""

    def test_missing_database(
        self,
        temp_calm_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test output when database doesn't exist."""
        # Ensure no database exists
        db_path = temp_calm_home / "metadata.db"
        if db_path.exists():
            db_path.unlink()

        # Patch get_db_path to return our temp path
        monkeypatch.setattr("calm.hooks.session_start.get_db_path", lambda: db_path)

        stdin = io.StringIO(json.dumps({"working_directory": "/test"}))
        stdout = io.StringIO()

        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            main()

        output = stdout.getvalue()
        assert "CALM available" in output
        assert "calm init" in output

    def test_with_database(
        self,
        db_with_tasks: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test output when database exists with tasks."""
        monkeypatch.setattr("calm.hooks.session_start.get_db_path", lambda: db_with_tasks)
        # Skip server start check
        monkeypatch.setattr("calm.hooks.session_start.ensure_server_running", lambda: True)

        stdin = io.StringIO(json.dumps({"working_directory": "/test/project"}))
        stdout = io.StringIO()

        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            main()

        output = stdout.getvalue()
        assert "CALM" in output
        assert "active task" in output

    def test_output_character_limit(
        self,
        db_with_active_ghap: Path,
        db_with_tasks: Path,
        temp_calm_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test output respects character limit."""
        # Use the tasks database
        monkeypatch.setattr("calm.hooks.session_start.get_db_path", lambda: db_with_tasks)
        monkeypatch.setattr("calm.hooks.session_start.ensure_server_running", lambda: True)

        stdin = io.StringIO(json.dumps({"working_directory": "/test/project"}))
        stdout = io.StringIO()

        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            main()

        output = stdout.getvalue()
        assert len(output) <= MAX_OUTPUT_CHARS

    def test_empty_working_directory_uses_cwd(
        self,
        temp_db: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that empty working_directory falls back to cwd."""
        monkeypatch.setattr("calm.hooks.session_start.get_db_path", lambda: temp_db)
        monkeypatch.setattr("calm.hooks.session_start.ensure_server_running", lambda: True)

        stdin = io.StringIO(json.dumps({"working_directory": ""}))
        stdout = io.StringIO()

        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            # Should not raise
            main()

        output = stdout.getvalue()
        assert "CALM" in output
