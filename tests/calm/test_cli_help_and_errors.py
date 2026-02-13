"""Tests for CLI --help output and error handling across all commands.

Verifies that:
1. Every command and subcommand produces valid --help output
2. Error messages for invalid arguments are clean (no Python tracebacks)
"""

import pytest
from click.testing import CliRunner

from calm.cli.main import cli


class TestTopLevelHelp:
    """Tests for top-level CLI --help output."""

    def test_calm_help(self) -> None:
        """Test calm --help lists all command groups."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        for cmd in [
            "backup", "counter", "gate", "init", "install",
            "review", "server", "session", "status", "task",
            "worker", "worktree",
        ]:
            assert cmd in result.output, f"Missing command: {cmd}"

    def test_version(self) -> None:
        """Test calm --version works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "calm" in result.output


class TestStatusHelp:
    """Tests for status subcommand --help output."""

    @pytest.mark.parametrize("subcmd", [
        [],  # top-level status
        ["health"],
        ["worktrees"],
        ["tasks"],
        ["workers"],
        ["counters"],
    ])
    def test_status_help(self, subcmd: list[str]) -> None:
        """Test status subcommand --help works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status"] + subcmd + ["--help"])
        assert result.exit_code == 0


class TestTaskHelp:
    """Tests for task subcommand --help output."""

    @pytest.mark.parametrize("subcmd", [
        [],  # top-level task
        ["create"],
        ["list"],
        ["show"],
        ["update"],
        ["transition"],
        ["delete"],
        ["next-id"],
    ])
    def test_task_help(self, subcmd: list[str]) -> None:
        """Test task subcommand --help works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["task"] + subcmd + ["--help"])
        assert result.exit_code == 0


class TestWorktreeHelp:
    """Tests for worktree subcommand --help output."""

    @pytest.mark.parametrize("subcmd", [
        [],  # top-level worktree
        ["create"],
        ["list"],
        ["path"],
        ["merge"],
        ["remove"],
        ["check-conflicts"],
    ])
    def test_worktree_help(self, subcmd: list[str]) -> None:
        """Test worktree subcommand --help works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["worktree"] + subcmd + ["--help"])
        assert result.exit_code == 0


class TestGateHelp:
    """Tests for gate subcommand --help output."""

    @pytest.mark.parametrize("subcmd", [
        [],  # top-level gate
        ["check"],
        ["list"],
    ])
    def test_gate_help(self, subcmd: list[str]) -> None:
        """Test gate subcommand --help works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["gate"] + subcmd + ["--help"])
        assert result.exit_code == 0


class TestWorkerHelp:
    """Tests for worker subcommand --help output."""

    @pytest.mark.parametrize("subcmd", [
        [],  # top-level worker
        ["start"],
        ["complete"],
        ["fail"],
        ["list"],
        ["cleanup"],
        ["context"],
        ["prompt"],
    ])
    def test_worker_help(self, subcmd: list[str]) -> None:
        """Test worker subcommand --help works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["worker"] + subcmd + ["--help"])
        assert result.exit_code == 0


class TestReviewHelp:
    """Tests for review subcommand --help output."""

    @pytest.mark.parametrize("subcmd", [
        [],  # top-level review
        ["record"],
        ["list"],
        ["check"],
        ["clear"],
    ])
    def test_review_help(self, subcmd: list[str]) -> None:
        """Test review subcommand --help works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review"] + subcmd + ["--help"])
        assert result.exit_code == 0


class TestCounterHelp:
    """Tests for counter subcommand --help output."""

    @pytest.mark.parametrize("subcmd", [
        [],  # top-level counter
        ["list"],
        ["get"],
        ["set"],
        ["increment"],
        ["add"],
        ["reset"],
    ])
    def test_counter_help(self, subcmd: list[str]) -> None:
        """Test counter subcommand --help works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["counter"] + subcmd + ["--help"])
        assert result.exit_code == 0


class TestBackupHelp:
    """Tests for backup subcommand --help output."""

    @pytest.mark.parametrize("subcmd", [
        [],  # top-level backup
        ["create"],
        ["list"],
        ["restore"],
        ["auto"],
        ["delete"],
    ])
    def test_backup_help(self, subcmd: list[str]) -> None:
        """Test backup subcommand --help works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["backup"] + subcmd + ["--help"])
        assert result.exit_code == 0


class TestSessionHelp:
    """Tests for session subcommand --help output."""

    @pytest.mark.parametrize("subcmd", [
        [],  # top-level session
        ["list"],
        ["show"],
        ["save"],
        ["pending"],
        ["resume"],
        ["next-commands"],
        ["journal"],
        ["journal", "list"],
        ["journal", "show"],
    ])
    def test_session_help(self, subcmd: list[str]) -> None:
        """Test session subcommand --help works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["session"] + subcmd + ["--help"])
        assert result.exit_code == 0


class TestServerHelp:
    """Tests for server subcommand --help output."""

    @pytest.mark.parametrize("subcmd", [
        [],  # top-level server
        ["start"],
        ["stop"],
        ["status"],
        ["restart"],
    ])
    def test_server_help(self, subcmd: list[str]) -> None:
        """Test server subcommand --help works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["server"] + subcmd + ["--help"])
        assert result.exit_code == 0


class TestInitAndInstallHelp:
    """Tests for init and install --help output."""

    def test_init_help(self) -> None:
        """Test init --help works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--help"])
        assert result.exit_code == 0

    def test_install_help(self) -> None:
        """Test install --help works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["install", "--help"])
        assert result.exit_code == 0
        assert "--dry-run" in result.output
        assert "--dev" in result.output


class TestMissingArgumentErrors:
    """Tests that missing required arguments produce clean error messages."""

    def test_task_create_missing_args(self) -> None:
        """Test task create with no args shows clean error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["task", "create"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output
        assert "Traceback" not in result.output

    def test_task_show_missing_args(self) -> None:
        """Test task show with no args shows clean error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["task", "show"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output
        assert "Traceback" not in result.output

    def test_task_transition_missing_args(self) -> None:
        """Test task transition with no args shows clean error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["task", "transition"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output
        assert "Traceback" not in result.output

    def test_counter_get_missing_args(self) -> None:
        """Test counter get with no args shows clean error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["counter", "get"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output
        assert "Traceback" not in result.output

    def test_counter_set_missing_args(self) -> None:
        """Test counter set with no args shows clean error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["counter", "set"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output
        assert "Traceback" not in result.output

    def test_worker_start_missing_args(self) -> None:
        """Test worker start with no args shows clean error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["worker", "start"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output
        assert "Traceback" not in result.output

    def test_worker_complete_missing_args(self) -> None:
        """Test worker complete with no args shows clean error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["worker", "complete"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output
        assert "Traceback" not in result.output

    def test_gate_check_missing_args(self) -> None:
        """Test gate check with no args shows clean error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["gate", "check"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output
        assert "Traceback" not in result.output

    def test_review_record_missing_args(self) -> None:
        """Test review record with no args shows clean error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "record"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output
        assert "Traceback" not in result.output

    def test_session_show_missing_args(self) -> None:
        """Test session show with no args shows clean error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["session", "show"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output
        assert "Traceback" not in result.output

    def test_backup_restore_missing_args(self) -> None:
        """Test backup restore with no args shows clean error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["backup", "restore"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output
        assert "Traceback" not in result.output

    def test_worktree_path_missing_args(self) -> None:
        """Test worktree path with no args shows clean error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["worktree", "path"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output
        assert "Traceback" not in result.output


class TestInvalidChoiceErrors:
    """Tests that invalid choice arguments produce clean error messages."""

    def test_task_next_id_invalid_prefix(self) -> None:
        """Test task next-id with invalid prefix shows clean error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["task", "next-id", "INVALID"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output or "not one of" in result.output
        assert "Traceback" not in result.output

    def test_review_record_invalid_type(self) -> None:
        """Test review record with invalid type shows clean error."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["review", "record", "SPEC-001", "invalid", "approved"]
        )

        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_review_record_invalid_result(self) -> None:
        """Test review record with invalid result shows clean error."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["review", "record", "SPEC-001", "spec", "invalid"]
        )

        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_task_create_invalid_type(self) -> None:
        """Test task create with invalid type shows clean error."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["task", "create", "T-001", "Test", "--type", "invalid"]
        )

        assert result.exit_code != 0
        assert "Traceback" not in result.output
