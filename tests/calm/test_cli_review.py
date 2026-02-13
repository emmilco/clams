"""Tests for CALM review CLI commands."""

from pathlib import Path

import pytest
from click.testing import CliRunner

import calm.config
import calm.orchestration.counters
import calm.orchestration.reviews
import calm.orchestration.tasks
import calm.orchestration.workers
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

    monkeypatch.setenv("CALM_HOME", str(calm_home))
    monkeypatch.setenv("CALM_DB_PATH", str(db_path))

    new_settings = CalmSettings()
    monkeypatch.setattr(calm.config, "settings", new_settings)
    monkeypatch.setattr(calm.orchestration.counters, "settings", new_settings)
    monkeypatch.setattr(calm.orchestration.tasks, "settings", new_settings)
    monkeypatch.setattr(calm.orchestration.workers, "settings", new_settings)
    monkeypatch.setattr(calm.orchestration.reviews, "settings", new_settings)

    monkeypatch.setattr(
        "calm.orchestration.project.detect_project_path",
        lambda: "/test/project",
    )

    return db_path


@pytest.fixture
def cli_with_task(cli_env: Path) -> Path:
    """Create a task for review tests."""
    runner = CliRunner()
    runner.invoke(cli, ["task", "create", "SPEC-001", "Test Task"])
    return cli_env


class TestReviewRecord:
    """Tests for calm review record command."""

    def test_record_approved(self, cli_with_task: Path) -> None:
        """Test recording an approved review."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["review", "record", "SPEC-001", "spec", "approved"]
        )

        assert result.exit_code == 0
        assert "Recorded spec review: approved" in result.output

    def test_record_changes_requested(self, cli_with_task: Path) -> None:
        """Test recording changes_requested review."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["review", "record", "SPEC-001", "spec", "changes_requested"]
        )

        assert result.exit_code == 0
        assert "Recorded spec review: changes_requested" in result.output
        assert "review cycle restarted" in result.output

    def test_record_nonexistent_task(self, cli_env: Path) -> None:
        """Test recording review for nonexistent task shows clean error."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["review", "record", "NONEXISTENT", "spec", "approved"]
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower()
        # Must not show raw Python traceback
        assert "Traceback" not in result.output

    def test_record_with_worker_id(self, cli_with_task: Path) -> None:
        """Test recording review with worker ID."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "review", "record", "SPEC-001", "code", "approved",
                "--worker", "W-test-123",
            ],
        )

        assert result.exit_code == 0
        assert "Recorded code review: approved" in result.output

    def test_record_missing_args(self) -> None:
        """Test recording review with missing arguments shows clean error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "record"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_record_invalid_review_type(self, cli_with_task: Path) -> None:
        """Test recording review with invalid type shows clean error."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["review", "record", "SPEC-001", "invalid_type", "approved"]
        )

        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_record_invalid_result(self, cli_with_task: Path) -> None:
        """Test recording review with invalid result shows clean error."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["review", "record", "SPEC-001", "spec", "invalid_result"]
        )

        assert result.exit_code != 0
        assert "Traceback" not in result.output


class TestReviewList:
    """Tests for calm review list command."""

    def test_list_empty(self, cli_with_task: Path) -> None:
        """Test listing when no reviews exist."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "list", "SPEC-001"])

        assert result.exit_code == 0
        assert "No reviews found" in result.output

    def test_list_reviews(self, cli_with_task: Path) -> None:
        """Test listing reviews."""
        runner = CliRunner()

        # Record reviews
        runner.invoke(cli, ["review", "record", "SPEC-001", "spec", "approved"])
        runner.invoke(cli, ["review", "record", "SPEC-001", "proposal", "approved"])

        result = runner.invoke(cli, ["review", "list", "SPEC-001"])

        assert result.exit_code == 0
        assert "spec" in result.output
        assert "proposal" in result.output


class TestReviewCheck:
    """Tests for calm review check command."""

    def test_check_fail(self, cli_with_task: Path) -> None:
        """Test check fails with insufficient reviews."""
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "check", "SPEC-001", "spec"])

        assert result.exit_code == 1
        assert "FAIL" in result.output

    def test_check_pass(self, cli_with_task: Path) -> None:
        """Test check passes with 2 approved reviews."""
        runner = CliRunner()

        # Record two approvals
        runner.invoke(cli, ["review", "record", "SPEC-001", "spec", "approved"])
        runner.invoke(cli, ["review", "record", "SPEC-001", "spec", "approved"])

        result = runner.invoke(cli, ["review", "check", "SPEC-001", "spec"])

        assert result.exit_code == 0
        assert "PASS" in result.output


class TestReviewClear:
    """Tests for calm review clear command."""

    def test_clear_reviews(self, cli_with_task: Path) -> None:
        """Test clearing reviews."""
        runner = CliRunner()

        # Record and clear reviews
        runner.invoke(cli, ["review", "record", "SPEC-001", "spec", "approved"])
        result = runner.invoke(cli, ["review", "clear", "SPEC-001", "--yes"])

        assert result.exit_code == 0
        assert "Cleared 1 reviews" in result.output
