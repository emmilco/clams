"""Tests for CALM hooks common utilities."""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from unittest.mock import patch

from calm.hooks.common import (
    get_calm_home,
    get_db_path,
    get_pid_path,
    get_session_id_path,
    get_tool_count_path,
    is_server_running,
    read_json_input,
    truncate_output,
    write_output,
)


class TestGetPaths:
    """Tests for path retrieval functions."""

    def test_get_calm_home_default(self) -> None:
        """Test get_calm_home returns default path."""
        home = get_calm_home()
        assert home == Path.home() / ".calm"

    def test_get_db_path_default(self) -> None:
        """Test get_db_path returns default path."""
        db_path = get_db_path()
        assert db_path == Path.home() / ".calm" / "metadata.db"

    def test_get_pid_path_default(self) -> None:
        """Test get_pid_path returns default path."""
        pid_path = get_pid_path()
        assert pid_path == Path.home() / ".calm" / "server.pid"

    def test_get_tool_count_path(self) -> None:
        """Test get_tool_count_path returns correct path."""
        count_path = get_tool_count_path()
        assert count_path == Path.home() / ".calm" / "tool_count"

    def test_get_session_id_path(self) -> None:
        """Test get_session_id_path returns correct path."""
        session_path = get_session_id_path()
        assert session_path == Path.home() / ".calm" / "session_id"


class TestReadJsonInput:
    """Tests for read_json_input function."""

    def test_read_valid_json(self) -> None:
        """Test reading valid JSON from stdin."""
        test_input = '{"key": "value", "number": 42}'
        with patch.object(sys, "stdin", io.StringIO(test_input)):
            result = read_json_input()
        assert result == {"key": "value", "number": 42}

    def test_read_empty_input(self) -> None:
        """Test reading empty input returns empty dict."""
        with patch.object(sys, "stdin", io.StringIO("")):
            result = read_json_input()
        assert result == {}

    def test_read_whitespace_input(self) -> None:
        """Test reading whitespace input returns empty dict."""
        with patch.object(sys, "stdin", io.StringIO("   \n  ")):
            result = read_json_input()
        assert result == {}

    def test_read_invalid_json(self) -> None:
        """Test reading invalid JSON returns empty dict."""
        with patch.object(sys, "stdin", io.StringIO("not valid json")):
            result = read_json_input()
        assert result == {}

    def test_read_non_dict_json(self) -> None:
        """Test reading non-dict JSON returns empty dict."""
        with patch.object(sys, "stdin", io.StringIO("[1, 2, 3]")):
            result = read_json_input()
        assert result == {}


class TestWriteOutput:
    """Tests for write_output function."""

    def test_write_non_empty(self) -> None:
        """Test writing non-empty output."""
        output = io.StringIO()
        with patch.object(sys, "stdout", output):
            write_output("test output")
        assert output.getvalue() == "test output"

    def test_write_empty(self) -> None:
        """Test writing empty output does nothing."""
        output = io.StringIO()
        with patch.object(sys, "stdout", output):
            write_output("")
        assert output.getvalue() == ""


class TestTruncateOutput:
    """Tests for truncate_output function."""

    def test_short_text_unchanged(self) -> None:
        """Test short text is not truncated."""
        text = "short text"
        result = truncate_output(text, 100)
        assert result == text

    def test_exact_limit_unchanged(self) -> None:
        """Test text at exact limit is not truncated."""
        text = "x" * 100
        result = truncate_output(text, 100)
        assert result == text

    def test_long_text_truncated(self) -> None:
        """Test long text is truncated with ellipsis."""
        text = "x" * 150
        result = truncate_output(text, 100)
        assert len(result) == 100
        assert result.endswith("...")

    def test_truncation_preserves_start(self) -> None:
        """Test truncation preserves start of text."""
        text = "IMPORTANT: " + "x" * 150
        result = truncate_output(text, 50)
        assert result.startswith("IMPORTANT: ")
        assert result.endswith("...")


class TestIsServerRunning:
    """Tests for is_server_running function."""

    def test_no_pid_file(self, tmp_path: Path) -> None:
        """Test returns False when PID file doesn't exist."""
        with patch("calm.hooks.common.get_pid_path", return_value=tmp_path / "server.pid"):
            assert is_server_running() is False

    def test_invalid_pid_file(self, tmp_path: Path) -> None:
        """Test returns False when PID file contains invalid data."""
        pid_file = tmp_path / "server.pid"
        pid_file.write_text("not a number")
        with patch("calm.hooks.common.get_pid_path", return_value=pid_file):
            assert is_server_running() is False

    def test_stale_pid_file(self, tmp_path: Path) -> None:
        """Test returns False when PID file contains dead process."""
        pid_file = tmp_path / "server.pid"
        # Use a very high PID that is unlikely to exist
        pid_file.write_text("999999999")
        with patch("calm.hooks.common.get_pid_path", return_value=pid_file):
            assert is_server_running() is False

    def test_valid_pid_file(self, tmp_path: Path) -> None:
        """Test returns True when PID file contains current process."""
        pid_file = tmp_path / "server.pid"
        # Use the current process PID which definitely exists
        pid_file.write_text(str(os.getpid()))
        with patch("calm.hooks.common.get_pid_path", return_value=pid_file):
            assert is_server_running() is True
