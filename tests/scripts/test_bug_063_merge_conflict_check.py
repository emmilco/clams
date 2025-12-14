"""Regression test for BUG-063: Add pre-merge conflict check.

This test verifies that claws-worktree merge performs a pre-merge conflict
check before attempting the merge operation. Without this check, merge
conflicts were only discovered at merge time, making resolution time-consuming
and error-prone.
"""

import re
from pathlib import Path


class TestBug063Regression:
    """Tests for BUG-063 fix: pre-merge conflict detection in claws-worktree."""

    def get_claws_worktree_script(self) -> str:
        """Read the claws-worktree script content."""
        # Navigate from tests/scripts/ to .claude/bin/
        scripts_dir = Path(__file__).parent.parent.parent / ".claude" / "bin"
        script_path = scripts_dir / "claws-worktree"
        return script_path.read_text()

    def test_has_conflict_check_function(self) -> None:
        """Verify claws-worktree has a check_merge_conflicts function.

        The pre-merge conflict check should be implemented as a separate
        function that can test for conflicts without actually merging.
        """
        source = self.get_claws_worktree_script()

        assert "check_merge_conflicts" in source, (
            "BUG-063 REGRESSION: claws-worktree missing check_merge_conflicts function. "
            "This function is needed to detect conflicts before attempting merge."
        )

    def test_conflict_check_uses_no_commit_merge(self) -> None:
        """Verify conflict check uses git merge --no-commit to test for conflicts.

        The safest way to check for conflicts is to attempt a merge with
        --no-commit flag, then abort it. This leaves the repo in a clean state.
        """
        source = self.get_claws_worktree_script()

        # Should use --no-commit --no-ff to test merge without committing
        assert re.search(r"git\s+merge\s+--no-commit", source), (
            "BUG-063 REGRESSION: claws-worktree should use 'git merge --no-commit' "
            "to test for conflicts before the actual merge."
        )

    def test_conflict_check_aborts_test_merge(self) -> None:
        """Verify conflict check aborts the test merge to restore clean state.

        After checking for conflicts, the test merge must be aborted to ensure
        the repository is left in a clean state regardless of result.
        """
        source = self.get_claws_worktree_script()

        assert "git merge --abort" in source, (
            "BUG-063 REGRESSION: claws-worktree must abort test merge after conflict check. "
            "Without this, the repo could be left in a dirty state."
        )

    def test_has_check_only_option(self) -> None:
        """Verify claws-worktree merge supports --check-only option.

        Users should be able to check for conflicts without attempting merge
        using: claws-worktree merge TASK-ID --check-only
        """
        source = self.get_claws_worktree_script()

        assert "--check-only" in source, (
            "BUG-063 REGRESSION: claws-worktree merge should support --check-only option "
            "to check for conflicts without actually merging."
        )

    def test_has_force_option(self) -> None:
        """Verify claws-worktree merge supports --force option.

        Users should be able to bypass conflict warning and attempt merge anyway
        using: claws-worktree merge TASK-ID --force
        """
        source = self.get_claws_worktree_script()

        assert "--force" in source, (
            "BUG-063 REGRESSION: claws-worktree merge should support --force option "
            "to proceed with merge even when conflicts are detected."
        )

    def test_shows_conflicting_files(self) -> None:
        """Verify conflict check outputs list of conflicting files.

        When conflicts are detected, the user should see which files conflict
        so they can resolve them before retrying the merge.
        """
        source = self.get_claws_worktree_script()

        # Should use git diff with conflict filter to get file list
        assert re.search(r"git\s+diff\s+--name-only", source), (
            "BUG-063 REGRESSION: claws-worktree should show conflicting file names "
            "using 'git diff --name-only' when conflicts are detected."
        )

    def test_provides_resolution_guidance(self) -> None:
        """Verify conflict warning provides guidance on resolution options.

        When conflicts are detected, the user should see helpful options:
        1. Rebase worktree on main first
        2. Resolve conflicts in worktree before merge
        3. Use --force to attempt merge anyway
        """
        source = self.get_claws_worktree_script()

        # Check for guidance text
        assert "Rebase" in source or "rebase" in source, (
            "BUG-063 REGRESSION: claws-worktree should suggest rebasing as a resolution option."
        )
        assert "Resolve" in source or "resolve" in source, (
            "BUG-063 REGRESSION: claws-worktree should suggest resolving conflicts in worktree."
        )

    def test_cmd_merge_calls_conflict_check(self) -> None:
        """Verify cmd_merge function calls the conflict check before merging.

        The merge command must check for conflicts before attempting the
        actual merge operation.
        """
        source = self.get_claws_worktree_script()

        # The cmd_merge function should call check_merge_conflicts
        # Look for the pattern where cmd_merge contains a call to check_merge_conflicts
        # This is a simpler check - verify both exist and cmd_merge is after the function
        assert "cmd_merge()" in source, (
            "BUG-063 REGRESSION: Could not find cmd_merge function in claws-worktree"
        )

        # Find positions
        cmd_merge_pos = source.find("cmd_merge()")
        check_conflicts_pos = source.find("check_merge_conflicts")

        assert check_conflicts_pos != -1, (
            "BUG-063 REGRESSION: check_merge_conflicts function not found"
        )

        # The check_merge_conflicts function should be defined before cmd_merge
        # and called within cmd_merge. Let's verify the call pattern exists.
        # Look for the call pattern: check_merge_conflicts "$task_id"
        call_pattern = re.search(
            r'check_merge_conflicts\s+"\$\w+"',
            source
        )

        assert call_pattern, (
            "BUG-063 REGRESSION: cmd_merge must call check_merge_conflicts before merging. "
            "Without this, conflicts are only discovered at merge time."
        )

        # Verify the call happens after cmd_merge function definition
        # (i.e., it's inside cmd_merge, not in the function definition itself)
        call_pos = call_pattern.start()
        assert call_pos > cmd_merge_pos, (
            "BUG-063 REGRESSION: check_merge_conflicts should be called inside cmd_merge"
        )

    def test_usage_documents_options(self) -> None:
        """Verify usage/help text documents --check-only and --force options."""
        source = self.get_claws_worktree_script()

        # Check usage function or header comments for option documentation
        assert "check-only" in source.lower(), (
            "BUG-063 REGRESSION: claws-worktree usage should document --check-only option"
        )
        assert "force" in source.lower(), (
            "BUG-063 REGRESSION: claws-worktree usage should document --force option"
        )
