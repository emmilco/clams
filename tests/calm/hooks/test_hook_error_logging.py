"""Regression tests for BUG-088: Hook error logging.

Verifies that:
1. Hook errors are logged to ~/.calm/hook_errors.log
2. Stdout remains empty when errors occur (does not break Claude Code)
3. Log rotation works when file exceeds 1 MB
4. log_hook_error never raises exceptions itself
"""

from __future__ import annotations

import io
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from calm.hooks.common import (
    _HOOK_LOG_MAX_BYTES,
    get_hook_error_log_path,
    log_hook_error,
)


# Helper for raising exceptions in lambdas
def _raise(exc: BaseException) -> None:
    raise exc


class TestGetHookErrorLogPath:
    """Tests for get_hook_error_log_path function."""

    def test_returns_path_in_calm_home(self) -> None:
        """Test returns hook_errors.log in CALM home directory."""
        log_path = get_hook_error_log_path()
        assert log_path.name == "hook_errors.log"
        assert log_path.parent.name == ".calm"

    def test_uses_custom_calm_home(
        self,
        temp_calm_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test uses configured CALM home directory."""
        monkeypatch.setattr(
            "calm.hooks.common.get_calm_home",
            lambda: temp_calm_home,
        )
        log_path = get_hook_error_log_path()
        assert log_path == temp_calm_home / "hook_errors.log"


class TestLogHookError:
    """Tests for log_hook_error function."""

    def test_creates_log_file(
        self,
        temp_calm_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test creates hook_errors.log when it does not exist."""
        monkeypatch.setattr(
            "calm.hooks.common.get_calm_home",
            lambda: temp_calm_home,
        )
        log_path = temp_calm_home / "hook_errors.log"
        assert not log_path.exists()

        try:
            raise ValueError("test error message")
        except ValueError as exc:
            log_hook_error("TestHook", exc)

        assert log_path.exists()
        content = log_path.read_text()
        assert "TestHook" in content
        assert "ValueError" in content
        assert "test error message" in content

    def test_appends_to_existing_log(
        self,
        temp_calm_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test appends to existing log file."""
        monkeypatch.setattr(
            "calm.hooks.common.get_calm_home",
            lambda: temp_calm_home,
        )
        log_path = temp_calm_home / "hook_errors.log"
        log_path.write_text("existing content\n")

        try:
            raise RuntimeError("new error")
        except RuntimeError as exc:
            log_hook_error("TestHook", exc)

        content = log_path.read_text()
        assert "existing content" in content
        assert "new error" in content

    def test_includes_timestamp(
        self,
        temp_calm_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test log entry includes UTC timestamp."""
        monkeypatch.setattr(
            "calm.hooks.common.get_calm_home",
            lambda: temp_calm_home,
        )
        log_path = temp_calm_home / "hook_errors.log"

        try:
            raise ValueError("timestamp test")
        except ValueError as exc:
            log_hook_error("TestHook", exc)

        content = log_path.read_text()
        # Timestamp format: [YYYY-MM-DDTHH:MM:SS.xxxxxxZ]
        assert content.startswith("[20")
        assert "Z]" in content

    def test_includes_hook_name(
        self,
        temp_calm_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test log entry includes hook name."""
        monkeypatch.setattr(
            "calm.hooks.common.get_calm_home",
            lambda: temp_calm_home,
        )
        log_path = temp_calm_home / "hook_errors.log"

        try:
            raise ValueError("hook name test")
        except ValueError as exc:
            log_hook_error("SessionStart.get_orphaned_ghap", exc)

        content = log_path.read_text()
        assert "hook=SessionStart.get_orphaned_ghap" in content

    def test_includes_exception_type_and_message(
        self,
        temp_calm_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test log entry includes exception type and message."""
        monkeypatch.setattr(
            "calm.hooks.common.get_calm_home",
            lambda: temp_calm_home,
        )
        log_path = temp_calm_home / "hook_errors.log"

        try:
            raise sqlite3.OperationalError("database is locked")
        except Exception as exc:
            log_hook_error("TestHook", exc)

        content = log_path.read_text()
        assert "exception=OperationalError" in content
        assert "message=database is locked" in content

    def test_includes_traceback(
        self,
        temp_calm_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test log entry includes traceback."""
        monkeypatch.setattr(
            "calm.hooks.common.get_calm_home",
            lambda: temp_calm_home,
        )
        log_path = temp_calm_home / "hook_errors.log"

        try:
            raise ValueError("traceback test")
        except ValueError as exc:
            log_hook_error("TestHook", exc)

        content = log_path.read_text()
        assert "Traceback" in content
        assert "traceback test" in content

    def test_never_raises_on_write_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test log_hook_error never raises, even when logging fails."""
        monkeypatch.setattr(
            "calm.hooks.common.get_calm_home",
            lambda: Path("/nonexistent/path/that/should/fail"),
        )

        # This must not raise
        try:
            raise ValueError("should not propagate")
        except ValueError as exc:
            log_hook_error("TestHook", exc)

    def test_creates_parent_directory(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test creates parent directory if it does not exist."""
        new_home = tmp_path / "new_calm_home"
        monkeypatch.setattr(
            "calm.hooks.common.get_calm_home",
            lambda: new_home,
        )

        try:
            raise ValueError("mkdir test")
        except ValueError as exc:
            log_hook_error("TestHook", exc)

        log_path = new_home / "hook_errors.log"
        assert log_path.exists()
        assert "mkdir test" in log_path.read_text()


class TestLogRotation:
    """Tests for log rotation behavior."""

    def test_rotates_when_exceeds_max_size(
        self,
        temp_calm_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test rotates log when it exceeds 1 MB."""
        monkeypatch.setattr(
            "calm.hooks.common.get_calm_home",
            lambda: temp_calm_home,
        )
        log_path = temp_calm_home / "hook_errors.log"
        backup_path = temp_calm_home / "hook_errors.log.1"

        # Create a log file that exceeds the max size
        log_path.write_text("x" * (_HOOK_LOG_MAX_BYTES + 1))

        try:
            raise ValueError("rotation test")
        except ValueError as exc:
            log_hook_error("TestHook", exc)

        # Original file should be rotated to .log.1
        assert backup_path.exists()
        assert backup_path.read_text().startswith("x" * 100)

        # New log file should contain only the new entry
        assert log_path.exists()
        new_content = log_path.read_text()
        assert "rotation test" in new_content
        assert not new_content.startswith("x")

    def test_no_rotation_under_max_size(
        self,
        temp_calm_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test does not rotate when under max size."""
        monkeypatch.setattr(
            "calm.hooks.common.get_calm_home",
            lambda: temp_calm_home,
        )
        log_path = temp_calm_home / "hook_errors.log"
        backup_path = temp_calm_home / "hook_errors.log.1"

        # Create a small log file
        log_path.write_text("small log\n")

        try:
            raise ValueError("no rotation test")
        except ValueError as exc:
            log_hook_error("TestHook", exc)

        # No backup should be created
        assert not backup_path.exists()

        # Original content should still be there plus new entry
        content = log_path.read_text()
        assert "small log" in content
        assert "no rotation test" in content

    def test_overwrites_previous_backup(
        self,
        temp_calm_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test rotation overwrites previous .log.1 backup."""
        monkeypatch.setattr(
            "calm.hooks.common.get_calm_home",
            lambda: temp_calm_home,
        )
        log_path = temp_calm_home / "hook_errors.log"
        backup_path = temp_calm_home / "hook_errors.log.1"

        # Create existing backup and oversized log
        backup_path.write_text("old backup content")
        log_path.write_text("y" * (_HOOK_LOG_MAX_BYTES + 1))

        try:
            raise ValueError("overwrite test")
        except ValueError as exc:
            log_hook_error("TestHook", exc)

        # Backup should now contain the rotated content (not old backup)
        backup_content = backup_path.read_text()
        assert backup_content.startswith("y")
        assert "old backup content" not in backup_content


class TestHookStdoutRemainsEmpty:
    """Tests verifying stdout stays empty when hooks encounter errors.

    This is critical -- hooks must NEVER write to stdout on error,
    or it will break Claude Code.
    """

    def test_session_start_db_error_silent(
        self,
        temp_calm_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test SessionStart outputs nothing on database error."""
        from calm.hooks.session_start import get_orphaned_ghap

        monkeypatch.setattr(
            "calm.hooks.common.get_calm_home",
            lambda: temp_calm_home,
        )

        bad_db = temp_calm_home / "bad.db"
        bad_db.write_text("not a database")

        result = get_orphaned_ghap(bad_db)
        assert result is None

        # Verify error was logged
        log_path = temp_calm_home / "hook_errors.log"
        assert log_path.exists()
        content = log_path.read_text()
        assert "SessionStart" in content

    def test_user_prompt_submit_error_silent_stdout(
        self,
        temp_calm_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test UserPromptSubmit outputs empty string on exception."""
        from calm.hooks.user_prompt_submit import main

        monkeypatch.setattr(
            "calm.hooks.common.get_calm_home",
            lambda: temp_calm_home,
        )

        # Make get_relevant_memories raise an unexpected exception
        monkeypatch.setattr(
            "calm.hooks.user_prompt_submit.get_relevant_memories",
            lambda *a: _raise(RuntimeError("simulated failure")),
        )

        # Set up a valid db path that exists
        db_path = temp_calm_home / "metadata.db"
        db_path.write_text("")  # just needs to exist for the path check
        monkeypatch.setattr(
            "calm.hooks.user_prompt_submit.get_db_path",
            lambda: db_path,
        )

        stdin = io.StringIO(json.dumps({"prompt": "test prompt"}))
        stdout = io.StringIO()

        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            main()

        # Stdout must be empty
        assert stdout.getvalue() == ""

        # Error should be logged
        log_path = temp_calm_home / "hook_errors.log"
        assert log_path.exists()
        content = log_path.read_text()
        assert "UserPromptSubmit" in content
        assert "simulated failure" in content

    def test_pre_tool_use_db_error_silent_stdout(
        self,
        temp_calm_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test PreToolUse outputs nothing on database error."""
        from calm.hooks.pre_tool_use import get_active_ghap

        monkeypatch.setattr(
            "calm.hooks.common.get_calm_home",
            lambda: temp_calm_home,
        )

        bad_db = temp_calm_home / "bad.db"
        bad_db.write_text("not a database")

        result = get_active_ghap(bad_db)
        assert result is None

    def test_post_tool_use_db_error_silent_stdout(
        self,
        temp_calm_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test PostToolUse outputs nothing on database error."""
        from calm.hooks.post_tool_use import get_active_ghap

        monkeypatch.setattr(
            "calm.hooks.common.get_calm_home",
            lambda: temp_calm_home,
        )

        bad_db = temp_calm_home / "bad.db"
        bad_db.write_text("not a database")

        result = get_active_ghap(bad_db)
        assert result is None


class TestHookErrorsAreLogged:
    """Tests verifying that specific hook error scenarios produce log entries."""

    def test_session_start_logs_db_error(
        self,
        temp_calm_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test SessionStart logs database errors."""
        from calm.hooks.session_start import get_active_tasks

        monkeypatch.setattr(
            "calm.hooks.common.get_calm_home",
            lambda: temp_calm_home,
        )

        bad_db = temp_calm_home / "bad.db"
        bad_db.write_text("not a database")

        get_active_tasks(bad_db, "/test/project")

        log_path = temp_calm_home / "hook_errors.log"
        assert log_path.exists()
        content = log_path.read_text()
        assert "SessionStart.get_active_tasks" in content

    def test_pre_tool_use_logs_read_count_error(
        self,
        temp_calm_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test PreToolUse logs tool count read errors."""
        from calm.hooks.pre_tool_use import read_tool_count

        monkeypatch.setattr(
            "calm.hooks.common.get_calm_home",
            lambda: temp_calm_home,
        )

        # Write invalid JSON to tool count file
        count_file = temp_calm_home / "tool_count"
        count_file.write_text("not valid json {{{")

        result = read_tool_count()
        assert result == (0, "")

        log_path = temp_calm_home / "hook_errors.log"
        assert log_path.exists()
        content = log_path.read_text()
        assert "PreToolUse.read_tool_count" in content
