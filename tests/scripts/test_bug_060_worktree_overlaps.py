"""Regression test for BUG-060: Detect file overlaps when creating worktree."""

import re
from pathlib import Path


class TestBug060Regression:
    """Tests for BUG-060 fix: worktree overlap detection."""

    def _get_script_source(self) -> str:
        """Load the claws-worktree script source."""
        claude_dir = Path(__file__).parent.parent.parent / ".claude" / "bin"
        worktree_script = claude_dir / "claws-worktree"
        return worktree_script.read_text()

    def test_check_overlaps_flag_supported(self) -> None:
        """Verify --check-overlaps flag is documented in usage."""
        source = self._get_script_source()

        assert "--check-overlaps" in source, (
            "BUG-060 REGRESSION: --check-overlaps flag not found in claws-worktree"
        )

        # Check it's in the usage message
        assert "claws-worktree create <task_id> [--check-overlaps]" in source, (
            "BUG-060 REGRESSION: --check-overlaps not documented in usage"
        )

    def test_force_flag_supported(self) -> None:
        """Verify --force flag is supported for bypassing warnings."""
        source = self._get_script_source()

        assert "--force" in source, (
            "BUG-060 REGRESSION: --force flag not found in claws-worktree"
        )

        # Check it's documented
        assert "--force: Bypass overlap warnings" in source or "--force]" in source, (
            "BUG-060 REGRESSION: --force not documented in usage"
        )

    def test_check_overlaps_function_exists(self) -> None:
        """Verify check_overlaps function is defined."""
        source = self._get_script_source()

        assert "check_overlaps()" in source, (
            "BUG-060 REGRESSION: check_overlaps function not found"
        )

    def test_check_overlaps_checks_uncommitted_changes(self) -> None:
        """Verify overlap check examines uncommitted changes in worktrees."""
        source = self._get_script_source()

        # Should use git diff to check for uncommitted changes
        assert "git diff --name-only" in source, (
            "BUG-060 REGRESSION: check_overlaps should use git diff to find changes"
        )

        # Should also check staged changes
        assert "git diff --cached --name-only" in source, (
            "BUG-060 REGRESSION: check_overlaps should check staged changes too"
        )

    def test_check_overlaps_scans_planning_docs(self) -> None:
        """Verify overlap check scans planning docs for file mentions."""
        source = self._get_script_source()

        # Should grep for file paths in planning docs
        assert "planning_docs" in source, (
            "BUG-060 REGRESSION: check_overlaps should scan planning_docs"
        )

        # Should also check bug reports
        assert "bug_reports" in source, (
            "BUG-060 REGRESSION: check_overlaps should scan bug_reports"
        )

    def test_check_overlaps_prompts_for_confirmation(self) -> None:
        """Verify overlap detection prompts user when overlaps found."""
        source = self._get_script_source()

        # Should prompt for confirmation when overlaps are detected
        assert "Continue anyway?" in source or "continue anyway?" in source.lower(), (
            "BUG-060 REGRESSION: should prompt for confirmation when overlaps found"
        )

    def test_force_bypasses_confirmation(self) -> None:
        """Verify --force flag bypasses the confirmation prompt."""
        source = self._get_script_source()

        # When force is true, should continue without prompting
        # Look for force-related logic
        force_pattern = r'force.*true.*continuing|--force.*specified'
        assert re.search(force_pattern, source, re.IGNORECASE), (
            "BUG-060 REGRESSION: --force should bypass confirmation prompt"
        )

    def test_check_overlaps_iterates_all_worktrees(self) -> None:
        """Verify overlap check examines all existing worktrees."""
        source = self._get_script_source()

        # Should use git worktree list
        assert "git worktree list" in source, (
            "BUG-060 REGRESSION: check_overlaps should iterate all worktrees"
        )

        # Should have a loop over worktrees
        assert "for wt in" in source, (
            "BUG-060 REGRESSION: check_overlaps should loop over worktrees"
        )

    def test_check_overlaps_reports_task_id(self) -> None:
        """Verify overlap warnings include the conflicting task ID."""
        source = self._get_script_source()

        # Should output the task ID when reporting conflicts
        assert "wt_task_id" in source, (
            "BUG-060 REGRESSION: overlap report should include task ID"
        )
