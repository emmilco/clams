"""Tests for CALM journal CLI commands."""

from pathlib import Path

import pytest
from click.testing import CliRunner

import calm.config
import calm.db.connection
import calm.orchestration.journal
from calm.cli.main import cli
from calm.config import CalmSettings
from calm.db.schema import init_database
from calm.orchestration.journal import store_journal_entry


@pytest.fixture
def cli_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up CLI environment with temp database."""
    home = tmp_path / ".calm"
    home.mkdir()

    db_path = home / "metadata.db"
    init_database(db_path)

    # Create sessions dir
    sessions_dir = home / "sessions"
    sessions_dir.mkdir()

    # Patch settings
    monkeypatch.setenv("CALM_HOME", str(home))
    monkeypatch.setenv("CALM_DB_PATH", str(db_path))

    new_settings = CalmSettings(home=home, db_path=db_path)
    monkeypatch.setattr(calm.config, "settings", new_settings)
    monkeypatch.setattr(calm.orchestration.journal, "settings", new_settings)
    monkeypatch.setattr(calm.db.connection, "settings", new_settings)

    return db_path


class TestJournalList:
    """Tests for calm session journal list command."""

    def test_list_empty(self, cli_env: Path) -> None:
        """Test listing when no entries exist."""
        runner = CliRunner()
        result = runner.invoke(cli, ["session", "journal", "list"])

        assert result.exit_code == 0
        assert "No journal entries found" in result.output

    def test_list_with_entries(self, cli_env: Path) -> None:
        """Test listing entries."""
        # Store entries directly
        store_journal_entry(
            summary="Test session 1",
            working_directory="/test/project1",
            db_path=cli_env,
        )
        store_journal_entry(
            summary="Test session 2",
            working_directory="/test/project2",
            db_path=cli_env,
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["session", "journal", "list"])

        assert result.exit_code == 0
        assert "Test session" in result.output
        assert "project1" in result.output
        assert "project2" in result.output

    def test_list_with_limit(self, cli_env: Path) -> None:
        """Test listing with limit."""
        for i in range(5):
            store_journal_entry(
                summary=f"Test session {i}",
                working_directory=f"/test/project{i}",
                db_path=cli_env,
            )

        runner = CliRunner()
        result = runner.invoke(cli, ["session", "journal", "list", "--limit", "2"])

        assert result.exit_code == 0
        # Should only show 2 entries

    def test_list_unreflected_only(self, cli_env: Path) -> None:
        """Test filtering for unreflected entries."""
        from calm.orchestration.journal import mark_entries_reflected

        entry1_id, _ = store_journal_entry(
            summary="Reflected entry",
            working_directory="/test/project1",
            db_path=cli_env,
        )
        store_journal_entry(
            summary="Unreflected entry",
            working_directory="/test/project2",
            db_path=cli_env,
        )

        # Mark first as reflected
        mark_entries_reflected([entry1_id], delete_logs=False, db_path=cli_env)

        runner = CliRunner()
        result = runner.invoke(
            cli, ["session", "journal", "list", "--unreflected"]
        )

        assert result.exit_code == 0
        assert "Unreflected entry" in result.output
        assert "[unreflected]" in result.output

    def test_list_filter_by_project(self, cli_env: Path) -> None:
        """Test filtering by project."""
        store_journal_entry(
            summary="Project1 session",
            working_directory="/test/myproject",
            db_path=cli_env,
        )
        store_journal_entry(
            summary="Project2 session",
            working_directory="/test/otherproject",
            db_path=cli_env,
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, ["session", "journal", "list", "--project", "myproject"]
        )

        assert result.exit_code == 0
        assert "Project1 session" in result.output
        assert "Project2 session" not in result.output


class TestJournalShow:
    """Tests for calm session journal show command."""

    def test_show_entry(self, cli_env: Path) -> None:
        """Test showing an entry."""
        entry_id, _ = store_journal_entry(
            summary="Detailed test summary",
            working_directory="/test/myproject",
            friction_points=["Issue 1", "Issue 2"],
            next_steps=["Step 1", "Step 2"],
            db_path=cli_env,
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["session", "journal", "show", entry_id])

        assert result.exit_code == 0
        assert entry_id in result.output
        assert "Detailed test summary" in result.output
        assert "myproject" in result.output
        assert "Issue 1" in result.output
        assert "Issue 2" in result.output
        assert "Step 1" in result.output
        assert "Step 2" in result.output

    def test_show_nonexistent_entry(self, cli_env: Path) -> None:
        """Test showing a nonexistent entry fails."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["session", "journal", "show", "00000000-0000-0000-0000-000000000000"]
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_show_with_log(self, cli_env: Path) -> None:
        """Test showing entry with session log."""
        # The sessions_dir should already be set up by cli_env fixture
        # and the settings patched properly
        entry_id, log_path = store_journal_entry(
            summary="Test summary",
            working_directory="/test/project",
            session_log_content='{"type": "test"}\n',
            db_path=cli_env,
        )

        # Verify log was written
        assert log_path is not None
        assert Path(log_path).exists()

        runner = CliRunner()
        result = runner.invoke(
            cli, ["session", "journal", "show", entry_id, "--log"]
        )

        assert result.exit_code == 0
        assert "Session Log" in result.output
        assert '{"type": "test"}' in result.output


class TestJournalCommandGroup:
    """Tests for the journal command group structure."""

    def test_journal_help(self, cli_env: Path) -> None:
        """Test journal command shows help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["session", "journal", "--help"])

        assert result.exit_code == 0
        assert "list" in result.output
        assert "show" in result.output
        assert "journal management" in result.output.lower()

    def test_journal_list_help(self, cli_env: Path) -> None:
        """Test journal list command shows help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["session", "journal", "list", "--help"])

        assert result.exit_code == 0
        assert "--unreflected" in result.output
        assert "--project" in result.output
        assert "--limit" in result.output

    def test_journal_show_help(self, cli_env: Path) -> None:
        """Test journal show command shows help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["session", "journal", "show", "--help"])

        assert result.exit_code == 0
        assert "--log" in result.output
        assert "ENTRY_ID" in result.output
