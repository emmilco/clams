"""Regression tests for BUG-084: Daemon uses sys.executable instead of venv Python.

Verifies that get_python_executable() correctly resolves the Python interpreter:
- Prefers VIRTUAL_ENV env var when set
- Detects venv via pyvenv.cfg in parent directories
- Falls back to sys.executable when no venv is detected
- daemon.start_daemon() and session_start.ensure_server_running() use it
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from calm.server.daemon import get_python_executable


class TestGetPythonExecutableVirtualEnv:
    """Tests for VIRTUAL_ENV env var detection (strategy 1)."""

    def test_uses_virtual_env_when_set(self, tmp_path: Path) -> None:
        """When VIRTUAL_ENV is set and bin/python exists, use it."""
        venv_dir = tmp_path / "my_venv"
        bin_dir = venv_dir / "bin"
        bin_dir.mkdir(parents=True)
        venv_python = bin_dir / "python"
        venv_python.touch()
        venv_python.chmod(0o755)

        with patch.dict(os.environ, {"VIRTUAL_ENV": str(venv_dir)}):
            result = get_python_executable()

        assert result == str(venv_python)

    def test_ignores_virtual_env_if_python_missing(self, tmp_path: Path) -> None:
        """When VIRTUAL_ENV is set but bin/python doesn't exist, skip it."""
        venv_dir = tmp_path / "broken_venv"
        venv_dir.mkdir()
        # No bin/python created

        with patch.dict(os.environ, {"VIRTUAL_ENV": str(venv_dir)}):
            # Should not return the broken venv path; falls through
            result = get_python_executable()

        assert result != str(venv_dir / "bin" / "python")

    def test_virtual_env_not_set_skips_strategy(self) -> None:
        """When VIRTUAL_ENV is not in env, strategy 1 is skipped."""
        env = os.environ.copy()
        env.pop("VIRTUAL_ENV", None)

        with patch.dict(os.environ, env, clear=True):
            # Should not raise; falls through to other strategies
            result = get_python_executable()
            assert isinstance(result, str)
            assert len(result) > 0


class TestGetPythonExecutablePyvenvCfg:
    """Tests for pyvenv.cfg detection (strategy 2)."""

    def test_detects_pyvenv_cfg_in_parent(self, tmp_path: Path) -> None:
        """When sys.executable is inside a dir with pyvenv.cfg above, use it."""
        # Create a fake venv structure:
        #   tmp_path/fake_venv/pyvenv.cfg
        #   tmp_path/fake_venv/bin/python
        venv_dir = tmp_path / "fake_venv"
        bin_dir = venv_dir / "bin"
        bin_dir.mkdir(parents=True)
        (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin\n")
        fake_python = bin_dir / "python"
        fake_python.touch()

        env = os.environ.copy()
        env.pop("VIRTUAL_ENV", None)

        with (
            patch.dict(os.environ, env, clear=True),
            patch("calm.server.daemon.sys") as mock_sys,
        ):
            mock_sys.executable = str(fake_python)
            result = get_python_executable()

        # Should return the resolved path of the fake python
        assert Path(result).name == "python"
        assert "fake_venv" in result

    def test_no_pyvenv_cfg_falls_through(self, tmp_path: Path) -> None:
        """When no pyvenv.cfg exists in any parent, fall through to strategy 3."""
        fake_python = tmp_path / "bin" / "python"
        fake_python.parent.mkdir(parents=True)
        fake_python.touch()

        env = os.environ.copy()
        env.pop("VIRTUAL_ENV", None)

        with (
            patch.dict(os.environ, env, clear=True),
            patch("calm.server.daemon.sys") as mock_sys,
        ):
            mock_sys.executable = str(fake_python)
            result = get_python_executable()

        # Falls back to sys.executable
        assert result == str(fake_python)


class TestGetPythonExecutableFallback:
    """Tests for the fallback to sys.executable (strategy 3)."""

    def test_fallback_returns_sys_executable(self, tmp_path: Path) -> None:
        """When no venv is detected at all, return sys.executable."""
        fake_python = tmp_path / "python3.11"
        fake_python.touch()

        env = os.environ.copy()
        env.pop("VIRTUAL_ENV", None)

        with (
            patch.dict(os.environ, env, clear=True),
            patch("calm.server.daemon.sys") as mock_sys,
        ):
            mock_sys.executable = str(fake_python)
            result = get_python_executable()

        assert result == str(fake_python)


class TestGetPythonExecutableIntegration:
    """Integration-level sanity checks."""

    def test_returns_valid_string(self) -> None:
        """get_python_executable() always returns a non-empty string."""
        result = get_python_executable()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returned_path_is_absolute(self) -> None:
        """The returned path should be absolute."""
        result = get_python_executable()
        assert os.path.isabs(result)

    def test_current_environment_returns_working_python(self) -> None:
        """In the current test environment, the result should be a real file."""
        result = get_python_executable()
        assert Path(result).exists(), (
            f"get_python_executable() returned {result!r} which does not exist"
        )


class TestDaemonUsesGetPythonExecutable:
    """Verify daemon.start_daemon() uses get_python_executable()."""

    def test_start_daemon_uses_helper(self) -> None:
        """start_daemon() must call get_python_executable() for the command."""
        from unittest.mock import MagicMock

        with (
            patch("calm.server.daemon.get_python_executable") as mock_get_py,
            patch("calm.server.daemon.get_log_file") as mock_log,
            patch("calm.server.daemon.get_pid_file") as mock_pid,
            patch("calm.server.daemon.subprocess.Popen") as mock_popen,
            patch("calm.server.daemon.settings") as mock_settings,
            patch("builtins.open", create=True),
            patch("builtins.print"),
        ):
            mock_get_py.return_value = "/fake/venv/bin/python"
            mock_settings.server_host = "127.0.0.1"
            mock_settings.server_port = 8080

            mock_log_path = MagicMock()
            mock_log_path.parent.mkdir = MagicMock()
            mock_log.return_value = mock_log_path

            mock_pid_path = MagicMock()
            mock_pid_path.parent.mkdir = MagicMock()
            mock_pid.return_value = mock_pid_path

            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            from calm.server.daemon import start_daemon

            start_daemon()

            mock_get_py.assert_called_once()
            # The first element of the command should be our resolved python
            cmd = mock_popen.call_args[0][0]
            assert cmd[0] == "/fake/venv/bin/python"


class TestSessionStartUsesGetPythonExecutable:
    """Verify session_start.ensure_server_running() uses get_python_executable()."""

    def test_ensure_server_running_uses_helper(self) -> None:
        """ensure_server_running() must use get_python_executable() for spawn."""
        with (
            patch(
                "calm.hooks.session_start.is_server_running", return_value=False
            ),
            patch(
                "calm.server.daemon.get_python_executable",
                return_value="/fake/venv/bin/python",
            ) as mock_get_py,
            patch("calm.hooks.session_start.subprocess.Popen") as mock_popen,
        ):
            from calm.hooks.session_start import ensure_server_running

            ensure_server_running()

            mock_get_py.assert_called_once()
            cmd = mock_popen.call_args[0][0]
            assert cmd[0] == "/fake/venv/bin/python"
