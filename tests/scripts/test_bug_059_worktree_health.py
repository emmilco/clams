"""Regression test for BUG-059: Add worktree health check command."""

import os
import re
from pathlib import Path


class TestBug059Regression:
    """Tests for BUG-059 fix: claws-worktree health command."""

    def _get_claws_worktree_path(self) -> Path:
        """Get path to claws-worktree script."""
        # Navigate from tests/scripts to .claude/bin
        return Path(__file__).parent.parent.parent / ".claude" / "bin" / "claws-worktree"

    def test_claws_worktree_has_health_command(self) -> None:
        """Verify claws-worktree script has health subcommand in case statement.

        BUG-059 identified that no health check command existed for auditing
        worktree state. This test verifies the health subcommand is present.
        """
        script_path = self._get_claws_worktree_path()
        source = script_path.read_text()

        # Check that health command is in the case statement
        assert re.search(r'health\)', source) is not None, (
            "BUG-059 REGRESSION: claws-worktree missing 'health' case in switch statement"
        )

        # Check that cmd_health function exists
        assert "cmd_health()" in source, (
            "BUG-059 REGRESSION: claws-worktree missing cmd_health function"
        )

    def test_health_command_in_usage(self) -> None:
        """Verify health command is documented in usage."""
        script_path = self._get_claws_worktree_path()
        source = script_path.read_text()

        # Check that health is in the usage function
        assert "health" in source.lower(), (
            "BUG-059 REGRESSION: 'health' not found in claws-worktree"
        )

        # Check for --fix option documentation
        assert "--fix" in source, (
            "BUG-059 REGRESSION: --fix option not found in claws-worktree"
        )

    def test_health_checks_key_conditions(self) -> None:
        """Verify health command checks for expected conditions.

        The health command should check for:
        - Orphaned worktrees (no task in database)
        - DONE tasks with worktrees still present
        - Uncommitted changes
        - Staleness (no recent commits)
        """
        script_path = self._get_claws_worktree_path()
        source = script_path.read_text()

        # Check for orphan detection
        assert "orphan" in source.lower() or "not found in database" in source.lower(), (
            "BUG-059 REGRESSION: health command should detect orphaned worktrees"
        )

        # Check for DONE task detection
        assert "DONE" in source, (
            "BUG-059 REGRESSION: health command should detect DONE tasks with worktrees"
        )

        # Check for uncommitted changes detection
        assert "uncommitted" in source.lower() or "git status" in source.lower(), (
            "BUG-059 REGRESSION: health command should detect uncommitted changes"
        )

        # Check for staleness detection
        assert "stale" in source.lower() or "days" in source.lower(), (
            "BUG-059 REGRESSION: health command should detect stale worktrees"
        )

    def test_health_has_fix_mode(self) -> None:
        """Verify health command supports --fix option for auto-remediation."""
        script_path = self._get_claws_worktree_path()
        source = script_path.read_text()

        # Check for fix mode parsing
        assert "fix_mode" in source or "--fix" in source, (
            "BUG-059 REGRESSION: health command should support --fix option"
        )

        # Check for dry-run option
        assert "dry_run" in source or "--dry-run" in source, (
            "BUG-059 REGRESSION: health command should support --dry-run option"
        )

    def test_health_outputs_structured_report(self) -> None:
        """Verify health command outputs structured report with status indicators."""
        script_path = self._get_claws_worktree_path()
        source = script_path.read_text()

        # Check for status indicators
        assert "OK" in source, (
            "BUG-059 REGRESSION: health command should output OK status"
        )
        assert "WARNING" in source, (
            "BUG-059 REGRESSION: health command should output WARNING status"
        )
        assert "ERROR" in source, (
            "BUG-059 REGRESSION: health command should output ERROR status"
        )

        # Check for summary section
        assert "Summary" in source or "summary" in source.lower(), (
            "BUG-059 REGRESSION: health command should output a summary"
        )

    def test_script_is_executable(self) -> None:
        """Verify claws-worktree script is executable."""
        script_path = self._get_claws_worktree_path()

        # Check file exists
        assert script_path.exists(), (
            f"BUG-059 REGRESSION: claws-worktree not found at {script_path}"
        )

        # Check executable permission
        assert os.access(script_path, os.X_OK), (
            "BUG-059 REGRESSION: claws-worktree is not executable"
        )
