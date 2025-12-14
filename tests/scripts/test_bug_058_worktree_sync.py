"""Regression test for BUG-058: Auto-sync pip after worktree merge."""

import re
from pathlib import Path


class TestBug058Regression:
    """Tests for BUG-058 fix: automatic dependency sync after merge."""

    def test_claws_worktree_syncs_dependencies_after_merge(self) -> None:
        """Verify claws-worktree merge syncs dependencies.

        After merging a worktree, dependencies should be automatically synced
        to avoid import errors when new packages were added in the worktree.
        """
        # Find the claws-worktree script
        claude_bin = Path(__file__).parent.parent.parent / ".claude" / "bin"
        worktree_script = claude_bin / "claws-worktree"
        source = worktree_script.read_text()

        # Should have dependency sync section after merge
        assert "Syncing dependencies" in source, (
            "BUG-058 REGRESSION: claws-worktree should print 'Syncing dependencies' "
            "message after merge"
        )

        # Should check for uv.lock first (preferred method)
        assert "uv.lock" in source, (
            "BUG-058 REGRESSION: claws-worktree should check for uv.lock"
        )
        assert "uv sync" in source, (
            "BUG-058 REGRESSION: claws-worktree should run 'uv sync' when uv.lock exists"
        )

        # Should fall back to requirements.txt
        assert "requirements.txt" in source, (
            "BUG-058 REGRESSION: claws-worktree should check for requirements.txt"
        )

        # Should fall back to pyproject.toml
        assert "pyproject.toml" in source, (
            "BUG-058 REGRESSION: claws-worktree should check for pyproject.toml"
        )
        assert "pip install -e ." in source, (
            "BUG-058 REGRESSION: claws-worktree should run 'pip install -e .' "
            "as fallback for pyproject.toml"
        )

    def test_claws_worktree_skip_sync_flag_exists(self) -> None:
        """Verify --skip-sync flag is supported for batch operations."""
        claude_bin = Path(__file__).parent.parent.parent / ".claude" / "bin"
        worktree_script = claude_bin / "claws-worktree"
        source = worktree_script.read_text()

        # Should support --skip-sync flag
        assert "--skip-sync" in source, (
            "BUG-058 REGRESSION: claws-worktree merge should support --skip-sync flag"
        )

        # Should have skip logic that respects the flag
        assert "skip_sync" in source, (
            "BUG-058 REGRESSION: claws-worktree should have skip_sync variable"
        )

        # Should print message when skipping
        assert "Skipping dependency sync" in source, (
            "BUG-058 REGRESSION: claws-worktree should print message when "
            "skipping dependency sync"
        )

    def test_claws_worktree_checks_uv_availability(self) -> None:
        """Verify claws-worktree checks if uv command is available."""
        claude_bin = Path(__file__).parent.parent.parent / ".claude" / "bin"
        worktree_script = claude_bin / "claws-worktree"
        source = worktree_script.read_text()

        # Should check if uv command exists before running it
        assert "command -v uv" in source, (
            "BUG-058 REGRESSION: claws-worktree should check if uv is in PATH "
            "before trying to run it"
        )

    def test_sync_happens_in_merge_function(self) -> None:
        """Verify dependency sync is in the cmd_merge function."""
        claude_bin = Path(__file__).parent.parent.parent / ".claude" / "bin"
        worktree_script = claude_bin / "claws-worktree"
        source = worktree_script.read_text()

        # Find cmd_merge function and verify sync is between merge and remove
        cmd_merge_match = re.search(
            r'cmd_merge\(\)\s*\{(.*?)\n\}',
            source,
            re.DOTALL
        )
        assert cmd_merge_match is not None, (
            "Could not find cmd_merge function in claws-worktree"
        )

        cmd_merge_body = cmd_merge_match.group(1)

        # Verify the order: merge -> sync -> remove worktree
        merge_pos = cmd_merge_body.find("git merge")
        sync_pos = cmd_merge_body.find("Syncing dependencies")
        remove_pos = cmd_merge_body.find("git worktree remove")

        assert merge_pos < sync_pos < remove_pos, (
            "BUG-058 REGRESSION: Dependency sync should happen after 'git merge' "
            "but before 'git worktree remove'"
        )
