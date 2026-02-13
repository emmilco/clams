"""Tests for CALM server CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

import calm.config
from calm.cli.main import cli
from calm.config import CalmSettings


@pytest.fixture
def cli_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up CLI environment with temp database."""
    calm_home = tmp_path / ".calm"
    calm_home.mkdir()

    db_path = calm_home / "metadata.db"

    monkeypatch.setenv("CALM_HOME", str(calm_home))
    monkeypatch.setenv("CALM_DB_PATH", str(db_path))
    monkeypatch.setenv("CALM_PID_FILE", str(calm_home / "server.pid"))
    monkeypatch.setenv("CALM_LOG_FILE", str(calm_home / "server.log"))

    new_settings = CalmSettings(home=calm_home, db_path=db_path)
    monkeypatch.setattr(calm.config, "settings", new_settings)

    # Patch the server settings import used by server.py
    import calm.cli.server as cli_server_mod

    monkeypatch.setattr(cli_server_mod, "settings", new_settings)

    return db_path


class TestServerStatus:
    """Tests for calm server status command."""

    def test_server_status_not_running(
        self, cli_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test server status when not running."""
        monkeypatch.setattr(
            "calm.server.daemon.is_server_running", lambda: False
        )
        monkeypatch.setattr("calm.server.daemon.get_server_pid", lambda: None)

        runner = CliRunner()
        result = runner.invoke(cli, ["server", "status"])

        assert result.exit_code == 0
        assert "not running" in result.output

    def test_server_status_running(
        self, cli_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test server status when running."""
        monkeypatch.setattr(
            "calm.server.daemon.is_server_running", lambda: True
        )
        monkeypatch.setattr("calm.server.daemon.get_server_pid", lambda: 12345)

        runner = CliRunner()
        result = runner.invoke(cli, ["server", "status"])

        assert result.exit_code == 0
        assert "running" in result.output.lower()
        assert "12345" in result.output


class TestServerStart:
    """Tests for calm server start command."""

    def test_start_already_running(
        self, cli_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test starting server when already running."""
        monkeypatch.setattr(
            "calm.server.daemon.is_server_running", lambda: True
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["server", "start"])

        assert result.exit_code == 0
        assert "already running" in result.output

    def test_start_daemon(
        self, cli_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test starting server as daemon."""
        monkeypatch.setattr(
            "calm.server.daemon.is_server_running", lambda: False
        )
        mock_start = MagicMock()
        monkeypatch.setattr("calm.server.daemon.start_daemon", mock_start)

        runner = CliRunner()
        result = runner.invoke(cli, ["server", "start"])

        assert result.exit_code == 0
        assert "Starting CALM server daemon" in result.output
        mock_start.assert_called_once()


class TestServerStop:
    """Tests for calm server stop command."""

    def test_stop_running(
        self, cli_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test stopping a running server."""
        monkeypatch.setattr("calm.server.daemon.stop_server", lambda: True)

        runner = CliRunner()
        result = runner.invoke(cli, ["server", "stop"])

        assert result.exit_code == 0
        assert "Server stopped" in result.output

    def test_stop_not_running(
        self, cli_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test stopping when server is not running."""
        monkeypatch.setattr("calm.server.daemon.stop_server", lambda: False)

        runner = CliRunner()
        result = runner.invoke(cli, ["server", "stop"])

        assert result.exit_code == 0
        assert "not running" in result.output


class TestServerRestart:
    """Tests for calm server restart command."""

    def test_restart_from_running(
        self, cli_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test restarting from running state."""
        monkeypatch.setattr(
            "calm.server.daemon.is_server_running", lambda: True
        )
        mock_stop = MagicMock(return_value=True)
        mock_start = MagicMock()
        monkeypatch.setattr("calm.server.daemon.stop_server", mock_stop)
        monkeypatch.setattr("calm.server.daemon.start_daemon", mock_start)

        runner = CliRunner()
        result = runner.invoke(cli, ["server", "restart"])

        assert result.exit_code == 0
        assert "Stopping" in result.output
        assert "Starting" in result.output
        mock_stop.assert_called_once()
        mock_start.assert_called_once()

    def test_restart_from_stopped(
        self, cli_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test restarting from stopped state."""
        monkeypatch.setattr(
            "calm.server.daemon.is_server_running", lambda: False
        )
        mock_start = MagicMock()
        monkeypatch.setattr("calm.server.daemon.start_daemon", mock_start)

        runner = CliRunner()
        result = runner.invoke(cli, ["server", "restart"])

        assert result.exit_code == 0
        assert "Starting" in result.output
        mock_start.assert_called_once()


class TestServerHelp:
    """Tests for server command help output."""

    def test_server_help(self) -> None:
        """Test server group --help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["server", "--help"])

        assert result.exit_code == 0
        assert "start" in result.output
        assert "stop" in result.output
        assert "status" in result.output
        assert "restart" in result.output

    def test_server_start_help(self) -> None:
        """Test server start --help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["server", "start", "--help"])

        assert result.exit_code == 0
        assert "--foreground" in result.output

    def test_server_stop_help(self) -> None:
        """Test server stop --help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["server", "stop", "--help"])

        assert result.exit_code == 0

    def test_server_status_help(self) -> None:
        """Test server status --help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["server", "status", "--help"])

        assert result.exit_code == 0

    def test_server_restart_help(self) -> None:
        """Test server restart --help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["server", "restart", "--help"])

        assert result.exit_code == 0
