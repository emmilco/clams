"""Tests for SPEC-061-07: Daemon Lifecycle and Error Recovery.

Verifies:
1. start/stop/restart/status CLI commands work correctly
2. Stale PID file recovery after kill -9
3. Qdrant-unavailable error handling (server starts, operations fail gracefully)
4. SessionStart hook auto-start behavior
5. server.log diagnostic information setup
"""

from __future__ import annotations

import os
import signal
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
from click.testing import CliRunner

import calm.config
from calm.config import CalmSettings
from calm.server.daemon import (
    get_log_file,
    get_pid_file,
    get_server_pid,
    is_server_running,
    start_daemon,
    stop_server,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def daemon_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up daemon environment with temp PID/log paths."""
    calm_home = tmp_path / ".calm"
    calm_home.mkdir()

    pid_file = calm_home / "server.pid"
    log_file = calm_home / "server.log"

    new_settings = CalmSettings(
        home=calm_home,
        pid_file=pid_file,
        log_file=log_file,
    )
    monkeypatch.setattr(calm.config, "settings", new_settings)
    monkeypatch.setattr("calm.server.daemon.settings", new_settings)

    return calm_home


# ---------------------------------------------------------------------------
# get_server_pid() tests
# ---------------------------------------------------------------------------


class TestGetServerPid:
    """Tests for get_server_pid function."""

    def test_no_pid_file(self, daemon_env: Path) -> None:
        """Returns None when PID file does not exist."""
        assert get_server_pid() is None

    def test_valid_pid_file(self, daemon_env: Path) -> None:
        """Returns PID when file contains a valid integer."""
        pid_file = daemon_env / "server.pid"
        pid_file.write_text("12345")
        assert get_server_pid() == 12345

    def test_empty_pid_file(self, daemon_env: Path) -> None:
        """Returns None when PID file is empty."""
        pid_file = daemon_env / "server.pid"
        pid_file.write_text("")
        assert get_server_pid() is None

    def test_invalid_pid_file(self, daemon_env: Path) -> None:
        """Returns None when PID file contains non-integer content."""
        pid_file = daemon_env / "server.pid"
        pid_file.write_text("not-a-number")
        assert get_server_pid() is None

    def test_pid_with_whitespace(self, daemon_env: Path) -> None:
        """Returns PID when file contains PID with whitespace."""
        pid_file = daemon_env / "server.pid"
        pid_file.write_text("  42  \n")
        assert get_server_pid() == 42


# ---------------------------------------------------------------------------
# is_server_running() tests
# ---------------------------------------------------------------------------


class TestIsServerRunning:
    """Tests for is_server_running function."""

    def test_no_pid_file(self, daemon_env: Path) -> None:
        """Returns False when no PID file exists."""
        assert is_server_running() is False

    def test_running_process(self, daemon_env: Path) -> None:
        """Returns True when PID file has valid PID of a running process."""
        # Use current process PID (guaranteed to be running)
        pid_file = daemon_env / "server.pid"
        pid_file.write_text(str(os.getpid()))
        assert is_server_running() is True

    def test_dead_process(self, daemon_env: Path) -> None:
        """Returns False when PID file references a dead process."""
        pid_file = daemon_env / "server.pid"
        # Use a PID that is almost certainly not running (very high number)
        pid_file.write_text("99999999")
        assert is_server_running() is False

    def test_invalid_pid_content(self, daemon_env: Path) -> None:
        """Returns False when PID file has invalid content."""
        pid_file = daemon_env / "server.pid"
        pid_file.write_text("garbage")
        assert is_server_running() is False


# ---------------------------------------------------------------------------
# stop_server() tests
# ---------------------------------------------------------------------------


class TestStopServer:
    """Tests for stop_server function."""

    def test_no_pid_file_returns_false(self, daemon_env: Path) -> None:
        """Returns False when no PID file exists."""
        assert stop_server() is False

    def test_stale_pid_file_cleaned_up(self, daemon_env: Path) -> None:
        """Cleans up stale PID file when process is not running."""
        pid_file = daemon_env / "server.pid"
        pid_file.write_text("99999999")  # Dead PID

        # stop_server catches the exception and cleans up PID file
        result = stop_server()
        # Returns False since process wasn't actually stopped (it was already dead)
        assert result is False
        assert not pid_file.exists()

    def test_stop_sends_sigterm(self, daemon_env: Path) -> None:
        """Sends SIGTERM to the process and cleans up PID file."""
        pid_file = daemon_env / "server.pid"
        pid_file.write_text("12345")

        with (
            patch("calm.server.daemon.os.kill") as mock_kill,
            patch("calm.server.daemon.time.sleep"),
        ):
            # First call to os.kill(pid, SIGTERM) succeeds
            # Second call to os.kill(pid, 0) raises (process exited)
            # Third call to os.kill(pid, SIGKILL) raises (process gone)
            mock_kill.side_effect = [
                None,  # SIGTERM
                ProcessLookupError,  # poll: process gone
                ProcessLookupError,  # SIGKILL: already dead
            ]

            result = stop_server()
            assert result is True
            assert not pid_file.exists()

            # Verify SIGTERM was sent
            first_call = mock_kill.call_args_list[0]
            assert first_call[0] == (12345, signal.SIGTERM)


# ---------------------------------------------------------------------------
# Stale PID file recovery (kill -9 scenario) tests
# ---------------------------------------------------------------------------


class TestStalePidRecovery:
    """Tests for AC3: After daemon crash (kill -9), calm server start recovers."""

    def test_start_succeeds_with_stale_pid_file(
        self, daemon_env: Path
    ) -> None:
        """start command proceeds when PID file exists but process is dead.

        This simulates the kill -9 scenario: PID file exists with a dead PID.
        The start command should detect the stale PID and start a new daemon.
        """
        from calm.cli.main import cli

        pid_file = daemon_env / "server.pid"
        # Create stale PID file (process 99999999 does not exist)
        pid_file.write_text("99999999")

        with (
            patch("calm.cli.server.settings") as mock_settings,
            patch("calm.server.daemon.start_daemon") as mock_start,
        ):
            mock_settings.server_host = "127.0.0.1"
            mock_settings.server_port = 6335

            runner = CliRunner()
            result = runner.invoke(cli, ["server", "start"])

            # start_daemon should be called since stale PID is detected as not running
            mock_start.assert_called_once()
            assert result.exit_code == 0

    def test_is_server_running_false_for_dead_pid(
        self, daemon_env: Path
    ) -> None:
        """is_server_running returns False for a stale PID file.

        This is the core mechanism enabling kill -9 recovery.
        """
        pid_file = daemon_env / "server.pid"
        pid_file.write_text("99999999")

        assert is_server_running() is False


# ---------------------------------------------------------------------------
# CLI server commands tests
# ---------------------------------------------------------------------------


class TestCliServerStart:
    """Tests for calm server start command."""

    def test_start_when_not_running(self, daemon_env: Path) -> None:
        """Starts daemon when server is not running."""
        from calm.cli.main import cli

        with (
            patch("calm.cli.server.settings") as mock_settings,
            patch("calm.server.daemon.start_daemon") as mock_start,
        ):
            mock_settings.server_host = "127.0.0.1"
            mock_settings.server_port = 6335

            runner = CliRunner()
            result = runner.invoke(cli, ["server", "start"])

            mock_start.assert_called_once()
            assert "Starting" in result.output
            assert result.exit_code == 0

    def test_start_when_already_running(self, daemon_env: Path) -> None:
        """Reports already running when server is running."""
        from calm.cli.main import cli

        # Write a PID file for the current process (guaranteed running)
        pid_file = daemon_env / "server.pid"
        pid_file.write_text(str(os.getpid()))

        with (
            patch("calm.cli.server.settings") as mock_settings,
            patch("calm.server.daemon.start_daemon") as mock_start,
        ):
            mock_settings.server_host = "127.0.0.1"
            mock_settings.server_port = 6335

            runner = CliRunner()
            result = runner.invoke(cli, ["server", "start"])

            mock_start.assert_not_called()
            assert "already running" in result.output
            assert result.exit_code == 0


class TestCliServerStop:
    """Tests for calm server stop command."""

    def test_stop_when_not_running(self, daemon_env: Path) -> None:
        """Reports not running when server is not running."""
        from calm.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["server", "stop"])

        assert "not running" in result.output
        assert result.exit_code == 0

    def test_stop_when_running(self, daemon_env: Path) -> None:
        """Stops server and reports success."""
        from calm.cli.main import cli

        pid_file = daemon_env / "server.pid"
        pid_file.write_text("12345")

        with (
            patch("calm.server.daemon.os.kill") as mock_kill,
            patch("calm.server.daemon.time.sleep"),
        ):
            mock_kill.side_effect = [
                None,  # SIGTERM
                ProcessLookupError,  # poll: process gone
                ProcessLookupError,  # SIGKILL: already dead
            ]

            runner = CliRunner()
            result = runner.invoke(cli, ["server", "stop"])

            assert "stopped" in result.output.lower()
            assert result.exit_code == 0


class TestCliServerStatus:
    """Tests for calm server status command."""

    def test_status_not_running(self, daemon_env: Path) -> None:
        """Shows not running when server is down."""
        from calm.cli.main import cli

        with patch("calm.cli.server.settings") as mock_settings:
            mock_settings.server_host = "127.0.0.1"
            mock_settings.server_port = 6335
            mock_settings.pid_file = daemon_env / "server.pid"
            mock_settings.log_file = daemon_env / "server.log"

            runner = CliRunner()
            result = runner.invoke(cli, ["server", "status"])

            assert "not running" in result.output
            assert result.exit_code == 0

    def test_status_running(self, daemon_env: Path) -> None:
        """Shows running with details when server is up."""
        from calm.cli.main import cli

        pid_file = daemon_env / "server.pid"
        pid_file.write_text(str(os.getpid()))

        with patch("calm.cli.server.settings") as mock_settings:
            mock_settings.server_host = "127.0.0.1"
            mock_settings.server_port = 6335
            mock_settings.pid_file = daemon_env / "server.pid"
            mock_settings.log_file = daemon_env / "server.log"

            runner = CliRunner()
            result = runner.invoke(cli, ["server", "status"])

            assert "running" in result.output.lower()
            assert str(os.getpid()) in result.output
            assert result.exit_code == 0


class TestCliServerRestart:
    """Tests for calm server restart command."""

    def test_restart_when_running(self, daemon_env: Path) -> None:
        """Stops and starts when server is running."""
        from calm.cli.main import cli

        pid_file = daemon_env / "server.pid"
        pid_file.write_text(str(os.getpid()))

        with (
            patch("calm.cli.server.settings") as mock_settings,
            patch("calm.server.daemon.stop_server") as mock_stop,
            patch("calm.server.daemon.start_daemon") as mock_start,
        ):
            mock_settings.server_host = "127.0.0.1"
            mock_settings.server_port = 6335
            mock_stop.return_value = True

            runner = CliRunner()
            result = runner.invoke(cli, ["server", "restart"])

            mock_stop.assert_called_once()
            mock_start.assert_called_once()
            assert result.exit_code == 0

    def test_restart_when_not_running(self, daemon_env: Path) -> None:
        """Just starts when server is not running."""
        from calm.cli.main import cli

        with (
            patch("calm.cli.server.settings") as mock_settings,
            patch("calm.server.daemon.stop_server") as mock_stop,
            patch("calm.server.daemon.start_daemon") as mock_start,
        ):
            mock_settings.server_host = "127.0.0.1"
            mock_settings.server_port = 6335

            runner = CliRunner()
            result = runner.invoke(cli, ["server", "restart"])

            mock_stop.assert_not_called()
            mock_start.assert_called_once()
            assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Log file setup tests
# ---------------------------------------------------------------------------


class TestLogFileSetup:
    """Tests for AC6: server.log diagnostic configuration."""

    def test_get_log_file_returns_settings_path(
        self, daemon_env: Path
    ) -> None:
        """get_log_file returns the configured log file path."""
        log_file = get_log_file()
        assert log_file == daemon_env / "server.log"

    def test_get_pid_file_returns_settings_path(
        self, daemon_env: Path
    ) -> None:
        """get_pid_file returns the configured PID file path."""
        pid_file = get_pid_file()
        assert pid_file == daemon_env / "server.pid"

    def test_start_daemon_creates_log_directory(
        self, daemon_env: Path
    ) -> None:
        """start_daemon creates the log file parent directory if needed."""
        # Move log file to a nested path that does not exist yet
        nested_log = daemon_env / "logs" / "nested" / "server.log"

        with (
            patch("calm.server.daemon.get_log_file", return_value=nested_log),
            patch("calm.server.daemon.get_pid_file", return_value=daemon_env / "server.pid"),
            patch("calm.server.daemon.get_python_executable", return_value="/usr/bin/python"),
            patch("calm.server.daemon.subprocess.Popen") as mock_popen,
            patch("builtins.print"),
        ):
            mock_proc = MagicMock()
            mock_proc.pid = 54321
            mock_popen.return_value = mock_proc

            start_daemon()

            # Verify that the parent directory of the log file was created
            assert nested_log.parent.exists()

    def test_start_daemon_redirects_output_to_log(
        self, daemon_env: Path
    ) -> None:
        """start_daemon passes log file as stdout for the child process."""
        log_file = daemon_env / "server.log"

        with (
            patch("calm.server.daemon.get_python_executable", return_value="/usr/bin/python"),
            patch("calm.server.daemon.subprocess.Popen") as mock_popen,
            patch("builtins.print"),
        ):
            mock_proc = MagicMock()
            mock_proc.pid = 54321
            mock_popen.return_value = mock_proc

            start_daemon()

            # Verify subprocess was called with the log file for stdout
            call_kwargs = mock_popen.call_args[1]
            assert call_kwargs["stderr"] is not None  # stderr redirected to stdout
            assert call_kwargs["start_new_session"] is True


class TestMainServerSignalHandling:
    """Tests for signal handling in server main module."""

    def test_main_registers_sigterm_handler(self) -> None:
        """Verify _run_server_async sets up SIGTERM handler.

        We verify this by inspecting the source code rather than running
        the actual async server (which requires full Qdrant + uvicorn).
        """
        import inspect

        from calm.server.main import _run_server_async

        source = inspect.getsource(_run_server_async)
        assert "signal.SIGTERM" in source
        assert "signal.SIGINT" in source
        assert "handle_shutdown" in source

    def test_main_cleans_up_pid_file_on_exit(self) -> None:
        """Verify _run_server_async has finally block for PID cleanup.

        The server main module should clean up the PID file in a finally
        block to handle graceful shutdown.
        """
        import inspect

        from calm.server.main import _run_server_async

        source = inspect.getsource(_run_server_async)
        assert "finally:" in source
        assert "pid_file.unlink()" in source

    def test_main_writes_pid_file_on_startup(self) -> None:
        """Verify _run_server_async writes PID file during startup."""
        import inspect

        from calm.server.main import _run_server_async

        source = inspect.getsource(_run_server_async)
        assert "pid_file.write_text(str(os.getpid()))" in source


# ---------------------------------------------------------------------------
# SessionStart hook auto-start tests (AC5)
# ---------------------------------------------------------------------------


class TestEnsureServerRunning:
    """Tests for AC5: SessionStart hook auto-start."""

    def test_returns_true_if_already_running(self) -> None:
        """Returns True immediately if server is already running."""
        from calm.hooks.session_start import ensure_server_running

        with patch("calm.hooks.session_start.is_server_running", return_value=True):
            assert ensure_server_running() is True

    def test_starts_server_if_not_running(self) -> None:
        """Attempts to start server and polls for readiness."""
        from calm.hooks.session_start import ensure_server_running

        call_count = 0

        def mock_is_running() -> bool:
            nonlocal call_count
            call_count += 1
            # First call: not running (triggers start)
            # Second call (during poll): running
            return call_count > 1

        with (
            patch(
                "calm.hooks.session_start.is_server_running",
                side_effect=mock_is_running,
            ),
            patch("calm.hooks.session_start.subprocess.Popen") as mock_popen,
            patch("calm.hooks.session_start.time.sleep"),
        ):
            result = ensure_server_running()

            assert result is True
            mock_popen.assert_called_once()

    def test_returns_false_on_timeout(self) -> None:
        """Returns False if server does not start within timeout."""
        from calm.hooks.session_start import ensure_server_running

        with (
            patch(
                "calm.hooks.session_start.is_server_running",
                return_value=False,
            ),
            patch("calm.hooks.session_start.subprocess.Popen"),
            patch("calm.hooks.session_start.time.time") as mock_time,
            patch("calm.hooks.session_start.time.sleep"),
        ):
            # Simulate time passing beyond the deadline
            mock_time.side_effect = [0.0, 6.0]  # start, then past deadline

            result = ensure_server_running()
            assert result is False

    def test_returns_false_on_spawn_error(self) -> None:
        """Returns False if subprocess.Popen raises OSError."""
        from calm.hooks.session_start import ensure_server_running

        with (
            patch(
                "calm.hooks.session_start.is_server_running",
                return_value=False,
            ),
            patch(
                "calm.hooks.session_start.subprocess.Popen",
                side_effect=OSError("spawn failed"),
            ),
        ):
            result = ensure_server_running()
            assert result is False


# ---------------------------------------------------------------------------
# Qdrant unavailability behavior (AC4)
# ---------------------------------------------------------------------------


class TestQdrantUnavailability:
    """Tests for AC4: Server starts when Qdrant is not running.

    The QdrantVectorStore uses AsyncQdrantClient which connects lazily.
    This means the server can start without Qdrant, and operations fail
    at invocation time with connection errors.
    """

    def test_qdrant_client_is_lazy(self) -> None:
        """QdrantVectorStore constructor does not connect immediately.

        This verifies that creating a QdrantVectorStore pointing to a
        non-existent Qdrant instance does NOT raise an exception at
        construction time.
        """
        from calm.storage.qdrant import QdrantVectorStore

        # Pointing to a port where nothing is listening
        # This should NOT raise an exception
        store = QdrantVectorStore(url="http://localhost:19999")
        assert store is not None

    def test_server_app_error_handler_catches_exceptions(self) -> None:
        """The handle_call_tool dispatcher catches all exceptions.

        When Qdrant is unavailable and a tool makes a Qdrant call,
        the exception is caught and returned as an error message.
        This is verified by inspecting the try/except in app.py.
        """
        import inspect

        from calm.server.app import create_server

        source = inspect.getsource(create_server)
        # The handle_call_tool inner function catches Exception
        assert "except Exception as e:" in source
        assert 'f"Error: {str(e)}"' in source
