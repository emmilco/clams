"""Tests for PreToolUse hook."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from calm.hooks.pre_tool_use import (
    DEFAULT_FREQUENCY,
    MAX_OUTPUT_CHARS,
    format_reminder,
    get_active_ghap,
    get_current_session_id,
    main,
    read_tool_count,
    write_tool_count,
)


class TestGetCurrentSessionId:
    """Tests for get_current_session_id function."""

    def test_no_session_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test returns empty string when no session ID in env."""
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        assert get_current_session_id() == ""

    def test_with_session_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test returns session ID from environment."""
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session-123")
        assert get_current_session_id() == "test-session-123"


class TestToolCountPersistence:
    """Tests for tool count file operations."""

    def test_read_missing_file(self, tool_count_file: Path) -> None:
        """Test reading non-existent file returns defaults."""
        with patch("calm.hooks.pre_tool_use.get_tool_count_path", return_value=tool_count_file):
            count, session_id = read_tool_count()
        assert count == 0
        assert session_id == ""

    def test_write_and_read(self, tool_count_file: Path) -> None:
        """Test writing and reading tool count."""
        with patch("calm.hooks.pre_tool_use.get_tool_count_path", return_value=tool_count_file):
            write_tool_count(5, "session-abc")
            count, session_id = read_tool_count()
        assert count == 5
        assert session_id == "session-abc"

    def test_read_corrupted_file(self, tool_count_file: Path) -> None:
        """Test reading corrupted file returns defaults."""
        tool_count_file.write_text("not valid json")
        with patch("calm.hooks.pre_tool_use.get_tool_count_path", return_value=tool_count_file):
            count, session_id = read_tool_count()
        assert count == 0
        assert session_id == ""

    def test_atomic_write(self, tool_count_file: Path) -> None:
        """Test write is atomic (uses temp file + rename)."""
        with patch("calm.hooks.pre_tool_use.get_tool_count_path", return_value=tool_count_file):
            write_tool_count(10, "session-xyz")

        # Verify the file contains valid JSON
        data = json.loads(tool_count_file.read_text())
        assert data["count"] == 10
        assert data["session_id"] == "session-xyz"


class TestGetActiveGhap:
    """Tests for get_active_ghap function."""

    def test_no_active_ghap(self, temp_db: Path) -> None:
        """Test returns None when no active GHAP."""
        result = get_active_ghap(temp_db)
        assert result is None

    def test_with_active_ghap(self, db_with_active_ghap: Path) -> None:
        """Test returns GHAP details when active."""
        result = get_active_ghap(db_with_active_ghap)
        assert result is not None
        assert result["goal"] == "Fix test failures"
        assert result["hypothesis"] == "Missing await on database call"
        assert result["prediction"] == "Tests will pass after adding await"

    def test_missing_database(self, tmp_path: Path) -> None:
        """Test returns None when database missing."""
        result = get_active_ghap(tmp_path / "nonexistent.db")
        assert result is None


class TestFormatReminder:
    """Tests for format_reminder function."""

    def test_format_reminder(self) -> None:
        """Test reminder formatting."""
        ghap = {
            "goal": "Fix test failures",
            "hypothesis": "Missing await",
            "prediction": "Tests will pass",
            "action": "Add await",
        }
        result = format_reminder(ghap)
        assert "## GHAP Check-in" in result
        assert "Fix test failures" in result
        assert "Missing await" in result
        assert "Tests will pass" in result
        assert "update_ghap" in result
        assert "resolve_ghap" in result

    def test_truncates_long_fields(self) -> None:
        """Test long fields are truncated to 80 chars."""
        ghap = {
            "goal": "x" * 200,
            "hypothesis": "y" * 200,
            "prediction": "z" * 200,
            "action": "action",
        }
        result = format_reminder(ghap)
        # Should be truncated at 80 chars
        assert "x" * 80 in result
        assert "x" * 81 not in result


class TestMain:
    """Tests for main entry point."""

    def test_no_tool_name(
        self,
        temp_db: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test outputs nothing when tool_name is missing."""
        monkeypatch.setattr("calm.hooks.pre_tool_use.get_db_path", lambda: temp_db)

        stdin = io.StringIO(json.dumps({}))
        stdout = io.StringIO()

        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            main()

        assert stdout.getvalue() == ""

    def test_below_frequency_threshold(
        self,
        temp_db: Path,
        tool_count_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test outputs nothing when below frequency threshold."""
        monkeypatch.setattr("calm.hooks.pre_tool_use.get_db_path", lambda: temp_db)
        monkeypatch.setattr("calm.hooks.pre_tool_use.get_tool_count_path", lambda: tool_count_file)
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

        # Start at count 5 (below DEFAULT_FREQUENCY=10)
        write_tool_count(5, "")

        stdin = io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}}))
        stdout = io.StringIO()

        with (
            patch.object(sys, "stdin", stdin),
            patch.object(sys, "stdout", stdout),
            patch("calm.hooks.pre_tool_use.get_tool_count_path", return_value=tool_count_file),
        ):
            main()

        assert stdout.getvalue() == ""

    def test_at_frequency_threshold_no_ghap(
        self,
        temp_db: Path,
        tool_count_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test outputs nothing at threshold when no active GHAP."""
        monkeypatch.setattr("calm.hooks.pre_tool_use.get_db_path", lambda: temp_db)
        monkeypatch.setattr("calm.hooks.pre_tool_use.get_tool_count_path", lambda: tool_count_file)
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

        # Set count just below threshold
        write_tool_count(DEFAULT_FREQUENCY - 1, "")

        stdin = io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}}))
        stdout = io.StringIO()

        with (
            patch.object(sys, "stdin", stdin),
            patch.object(sys, "stdout", stdout),
            patch("calm.hooks.pre_tool_use.get_tool_count_path", return_value=tool_count_file),
        ):
            main()

        # No output because no active GHAP
        assert stdout.getvalue() == ""

    def test_at_frequency_threshold_with_ghap(
        self,
        db_with_active_ghap: Path,
        tool_count_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test outputs reminder at threshold when GHAP is active."""
        monkeypatch.setattr("calm.hooks.pre_tool_use.get_db_path", lambda: db_with_active_ghap)
        monkeypatch.setattr("calm.hooks.pre_tool_use.get_tool_count_path", lambda: tool_count_file)
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

        # Set count just below threshold
        write_tool_count(DEFAULT_FREQUENCY - 1, "")

        stdin = io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}}))
        stdout = io.StringIO()

        with (
            patch.object(sys, "stdin", stdin),
            patch.object(sys, "stdout", stdout),
            patch("calm.hooks.pre_tool_use.get_tool_count_path", return_value=tool_count_file),
        ):
            main()

        output = stdout.getvalue()
        assert "GHAP Check-in" in output
        assert "Fix test failures" in output

    def test_session_change_resets_counter(
        self,
        db_with_active_ghap: Path,
        tool_count_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test counter resets when session changes."""
        monkeypatch.setattr("calm.hooks.pre_tool_use.get_db_path", lambda: db_with_active_ghap)
        monkeypatch.setattr("calm.hooks.pre_tool_use.get_tool_count_path", lambda: tool_count_file)
        monkeypatch.setenv("CLAUDE_SESSION_ID", "new-session")

        # Set high count for old session
        write_tool_count(20, "old-session")

        stdin = io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}}))
        stdout = io.StringIO()

        with (
            patch.object(sys, "stdin", stdin),
            patch.object(sys, "stdout", stdout),
            patch("calm.hooks.pre_tool_use.get_tool_count_path", return_value=tool_count_file),
        ):
            main()

        # Should NOT output reminder because counter was reset to 0
        # (new count = 1, below threshold)
        assert stdout.getvalue() == ""

        # Verify counter was reset
        count, session = read_tool_count()
        assert session == "new-session"
        assert count == 1

    def test_output_character_limit(
        self,
        db_with_active_ghap: Path,
        tool_count_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test output respects character limit."""
        monkeypatch.setattr("calm.hooks.pre_tool_use.get_db_path", lambda: db_with_active_ghap)
        monkeypatch.setattr("calm.hooks.pre_tool_use.get_tool_count_path", lambda: tool_count_file)
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

        write_tool_count(DEFAULT_FREQUENCY - 1, "")

        stdin = io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}}))
        stdout = io.StringIO()

        with (
            patch.object(sys, "stdin", stdin),
            patch.object(sys, "stdout", stdout),
            patch("calm.hooks.pre_tool_use.get_tool_count_path", return_value=tool_count_file),
        ):
            main()

        output = stdout.getvalue()
        assert len(output) <= MAX_OUTPUT_CHARS
