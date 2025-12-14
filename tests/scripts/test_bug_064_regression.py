"""Regression test for BUG-064: Auto-commit staged changes on wrapup."""

import re
from pathlib import Path


class TestBug064Regression:
    """Tests for BUG-064 fix: auto-commit staged changes in worktrees on session save."""

    def test_claws_session_has_auto_commit_logic(self) -> None:
        """Verify claws-session contains auto-commit logic for staged changes.

        The bug was that staged changes in worktrees were left uncommitted
        when a session ended, causing issues in the next session.
        The fix adds auto-commit logic to claws-session save.
        """
        # Find the claws-session script
        script_path = Path(__file__).parent.parent.parent / ".claude" / "bin" / "claws-session"
        source = script_path.read_text()

        # Verify auto-commit flag exists
        assert "--no-auto-commit" in source, (
            "BUG-064 REGRESSION: claws-session should have --no-auto-commit flag"
        )

        # Verify staged change detection logic exists
        assert "git -C" in source and "diff --cached" in source, (
            "BUG-064 REGRESSION: claws-session should check for staged changes with 'git diff --cached'"
        )

        # Verify auto-commit message exists
        assert "WIP: Auto-commit at session end" in source, (
            "BUG-064 REGRESSION: claws-session should commit with WIP message"
        )

        # Verify unstaged warning exists
        assert "has unstaged changes" in source, (
            "BUG-064 REGRESSION: claws-session should warn about unstaged changes"
        )

    def test_claws_session_iterates_worktrees(self) -> None:
        """Verify claws-session iterates over all worktrees."""
        script_path = Path(__file__).parent.parent.parent / ".claude" / "bin" / "claws-session"
        source = script_path.read_text()

        # Check for worktree iteration
        assert "WORKTREE_DIR" in source, (
            "BUG-064 REGRESSION: claws-session should use WORKTREE_DIR variable"
        )

        # Check for loop over worktrees
        worktree_loop_pattern = r'for worktree in.*WORKTREE_DIR'
        assert re.search(worktree_loop_pattern, source), (
            "BUG-064 REGRESSION: claws-session should loop over worktrees"
        )

    def test_claws_session_appends_to_handoff(self) -> None:
        """Verify auto-commit information is appended to handoff content."""
        script_path = Path(__file__).parent.parent.parent / ".claude" / "bin" / "claws-session"
        source = script_path.read_text()

        # Check for handoff content modification
        assert "Auto-Committed Worktrees" in source, (
            "BUG-064 REGRESSION: claws-session should add 'Auto-Committed Worktrees' section"
        )

        assert "Worktrees with Unstaged Changes" in source, (
            "BUG-064 REGRESSION: claws-session should add 'Worktrees with Unstaged Changes' section"
        )

    def test_auto_commit_default_enabled(self) -> None:
        """Verify auto-commit is enabled by default (opt-out, not opt-in)."""
        script_path = Path(__file__).parent.parent.parent / ".claude" / "bin" / "claws-session"
        source = script_path.read_text()

        # Check that auto_commit defaults to 1 (enabled)
        assert "local auto_commit=1" in source, (
            "BUG-064 REGRESSION: auto-commit should default to enabled (auto_commit=1)"
        )

        # Check that --no-auto-commit sets it to 0
        assert re.search(r'--no-auto-commit\).*\n.*auto_commit=0', source), (
            "BUG-064 REGRESSION: --no-auto-commit should disable auto-commit"
        )
