"""Tests for CALM session CLI commands."""

from pathlib import Path

import pytest
from click.testing import CliRunner

import calm.config
import calm.orchestration.sessions
import calm.orchestration.tasks
from calm.cli.main import cli
from calm.config import CalmSettings
from calm.db.schema import init_database


@pytest.fixture
def cli_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up CLI environment with temp database."""
    calm_home = tmp_path / ".calm"
    calm_home.mkdir()

    db_path = calm_home / "metadata.db"
    init_database(db_path)

    # Patch settings
    monkeypatch.setenv("CALM_HOME", str(calm_home))
    monkeypatch.setenv("CALM_DB_PATH", str(db_path))

    new_settings = CalmSettings(home=calm_home, db_path=db_path)
    monkeypatch.setattr(calm.config, "settings", new_settings)
    monkeypatch.setattr(calm.orchestration.sessions, "settings", new_settings)
    monkeypatch.setattr(calm.orchestration.tasks, "settings", new_settings)

    # Mock project path detection
    monkeypatch.setattr(
        "calm.orchestration.project.detect_project_path",
        lambda: "/test/project",
    )

    return db_path


class TestSessionSave:
    """Tests for calm session save command."""

    def test_save_session(self, cli_env: Path) -> None:
        """Test saving a session handoff."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["session", "save"], input="Test handoff content\n"
        )

        assert result.exit_code == 0
        assert "Saved session" in result.output

    def test_save_session_with_continuation(self, cli_env: Path) -> None:
        """Test saving a session marked for continuation."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["session", "save", "--continue"],
            input="Continue this work\n"
        )

        assert result.exit_code == 0
        assert "Saved session" in result.output
        assert "continuation" in result.output.lower()

    def test_save_session_empty_content(self, cli_env: Path) -> None:
        """Test saving session with empty content fails."""
        runner = CliRunner()
        result = runner.invoke(cli, ["session", "save"], input="\n")

        assert result.exit_code != 0
        assert "No content" in result.output


class TestSessionList:
    """Tests for calm session list command."""

    def test_list_sessions_empty(self, cli_env: Path) -> None:
        """Test listing sessions when none exist."""
        runner = CliRunner()
        result = runner.invoke(cli, ["session", "list"])

        assert result.exit_code == 0
        assert "No sessions found" in result.output

    def test_list_sessions_with_sessions(self, cli_env: Path) -> None:
        """Test listing sessions after creating some."""
        runner = CliRunner()

        # Create sessions
        runner.invoke(cli, ["session", "save"], input="Session 1\n")
        runner.invoke(cli, ["session", "save"], input="Session 2\n")

        result = runner.invoke(cli, ["session", "list"])

        assert result.exit_code == 0
        # Should show session IDs


class TestSessionShow:
    """Tests for calm session show command."""

    def test_show_session(self, cli_env: Path) -> None:
        """Test showing a session."""
        runner = CliRunner()

        # Create session and get ID
        save_result = runner.invoke(
            cli, ["session", "save"], input="Test content\n"
        )
        # Extract session ID from output
        session_id = save_result.output.split(":")[-1].strip()

        result = runner.invoke(cli, ["session", "show", session_id])

        assert result.exit_code == 0
        assert "Session:" in result.output
        assert "Test content" in result.output

    def test_show_nonexistent_session(self, cli_env: Path) -> None:
        """Test showing nonexistent session fails."""
        runner = CliRunner()
        result = runner.invoke(cli, ["session", "show", "nonexistent"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()


class TestSessionPending:
    """Tests for calm session pending command."""

    def test_pending_no_session(self, cli_env: Path) -> None:
        """Test when there's no pending session."""
        runner = CliRunner()
        result = runner.invoke(cli, ["session", "pending"])

        assert result.exit_code == 0
        assert "No pending handoff" in result.output

    def test_pending_with_session(self, cli_env: Path) -> None:
        """Test showing pending session."""
        runner = CliRunner()

        # Create session marked for continuation
        runner.invoke(
            cli, ["session", "save", "--continue"],
            input="Continue this\n"
        )

        result = runner.invoke(cli, ["session", "pending"])

        assert result.exit_code == 0
        assert "Continue this" in result.output


class TestSessionResume:
    """Tests for calm session resume command."""

    def test_resume_session(self, cli_env: Path) -> None:
        """Test resuming a session."""
        runner = CliRunner()

        # Create session
        save_result = runner.invoke(
            cli, ["session", "save", "--continue"],
            input="Resume this\n"
        )

        # Extract session ID - output is "Saved session: <id>\nMarked for continuation"
        for line in save_result.output.split("\n"):
            if "Saved session:" in line:
                session_id = line.split(":")[-1].strip()
                break

        result = runner.invoke(cli, ["session", "resume", session_id])

        assert result.exit_code == 0
        assert "resumed" in result.output.lower()

    def test_resume_nonexistent_session(self, cli_env: Path) -> None:
        """Test resuming nonexistent session fails."""
        runner = CliRunner()
        result = runner.invoke(cli, ["session", "resume", "nonexistent"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()


class TestSessionNextCommands:
    """Tests for calm session next-commands command."""

    def test_next_commands_no_tasks(self, cli_env: Path) -> None:
        """Test next commands when no tasks exist for this project."""
        runner = CliRunner()
        result = runner.invoke(cli, ["session", "next-commands"])

        assert result.exit_code == 0
        # With no tasks in this fresh database, we should see "No active tasks"
        # or get the command markdown output
        assert "Next Commands" in result.output or "No active tasks" in result.output
