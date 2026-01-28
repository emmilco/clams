"""Regression test for BUG-066: claws-worktree merge doesn't update task phase.

This test verifies that claws-worktree merge automatically updates the task
phase after a successful merge. Without this fix, tasks remained in stale
phases (like MERGED or INTEGRATE) after the worktree was removed, causing
database drift and incorrect status reports.

The fix:
- Bug tasks: auto-transition to DONE after merge
- Feature tasks: auto-transition to VERIFY after merge
"""

import re
from pathlib import Path


class TestBug066Regression:
    """Tests for BUG-066 fix: auto-transition phase on merge."""

    def get_claws_worktree_script(self) -> str:
        """Read the claws-worktree script content."""
        # Navigate from tests/scripts/ to .claude/bin/
        scripts_dir = Path(__file__).parent.parent.parent / ".claude" / "bin"
        script_path = scripts_dir / "claws-worktree"
        return script_path.read_text()

    def test_merge_looks_up_task_type(self) -> None:
        """Verify cmd_merge queries task_type before merge.

        To determine the correct post-merge phase, the merge command must
        look up the task_type (bug vs feature) from the database.
        """
        source = self.get_claws_worktree_script()

        # Should query task_type from database
        assert re.search(r"SELECT\s+task_type", source, re.IGNORECASE), (
            "BUG-066 REGRESSION: claws-worktree merge must query task_type "
            "to determine correct post-merge phase (DONE for bugs, VERIFY for features)."
        )

    def test_merge_updates_phase_in_database(self) -> None:
        """Verify cmd_merge updates phase column after successful merge.

        The critical fix: after clearing worktree_path, the merge command
        must also update the phase column to prevent database drift.
        """
        source = self.get_claws_worktree_script()

        # Should have an UPDATE statement that sets phase
        assert re.search(r"UPDATE\s+tasks\s+SET\s+phase", source, re.IGNORECASE), (
            "BUG-066 REGRESSION: claws-worktree merge must UPDATE phase column. "
            "Without this, tasks remain in stale phases after merge."
        )

    def test_bug_tasks_transition_to_done(self) -> None:
        """Verify bug tasks transition to DONE phase after merge.

        Bug workflow ends with merge, so the phase should go directly to DONE.
        """
        source = self.get_claws_worktree_script()

        # Should have logic that sets phase to DONE for bugs
        # Look for the pattern: if bug then DONE
        assert re.search(r'task_type.*bug.*DONE|bug.*new_phase.*DONE', source, re.IGNORECASE | re.DOTALL), (
            "BUG-066 REGRESSION: Bug tasks must transition to DONE after merge. "
            "The merge is the final step in bug workflow."
        )

    def test_feature_tasks_transition_to_verify(self) -> None:
        """Verify feature tasks transition to VERIFY phase after merge.

        Feature workflow has a VERIFY phase after merge (run tests on main,
        acceptance verification), so phase should go to VERIFY, not DONE.
        """
        source = self.get_claws_worktree_script()

        # Should have logic that sets phase to VERIFY for features (non-bugs)
        assert "VERIFY" in source, (
            "BUG-066 REGRESSION: Feature tasks must transition to VERIFY after merge. "
            "VERIFY phase runs on main after merge for acceptance testing."
        )

    def test_logs_phase_transition(self) -> None:
        """Verify merge command logs the phase transition for visibility.

        Users should see what phase transition happened, e.g.:
        'Task phase updated: MERGED -> DONE'
        """
        source = self.get_claws_worktree_script()

        # Should echo/print the phase transition
        assert re.search(r'phase.*updated|Task phase', source, re.IGNORECASE), (
            "BUG-066 REGRESSION: Merge should log phase transition for visibility. "
            "Users need to know the automatic transition happened."
        )

    def test_phase_update_happens_after_worktree_cleanup(self) -> None:
        """Verify phase update occurs after worktree is removed.

        The phase update must happen after the worktree is successfully
        removed, not before, to avoid partial state.
        """
        source = self.get_claws_worktree_script()

        # Find positions of worktree removal and phase update
        worktree_remove = source.find("git worktree remove")
        phase_update = source.find("UPDATE tasks SET phase")

        assert worktree_remove != -1, (
            "BUG-066 REGRESSION: Could not find worktree removal in script"
        )
        assert phase_update != -1, (
            "BUG-066 REGRESSION: Could not find phase update in script"
        )

        # Phase update should come after worktree removal
        # (within cmd_merge function, after cleanup)
        # Find cmd_merge function to scope the check
        cmd_merge_start = source.find("cmd_merge()")
        assert cmd_merge_start != -1, "Could not find cmd_merge function"

        # Both operations should be in cmd_merge and phase update after removal
        cmd_merge_section = source[cmd_merge_start:]
        remove_in_merge = cmd_merge_section.find("git worktree remove")
        phase_in_merge = cmd_merge_section.find("UPDATE tasks SET phase")

        assert remove_in_merge != -1, (
            "BUG-066 REGRESSION: worktree removal not found in cmd_merge"
        )
        assert phase_in_merge != -1, (
            "BUG-066 REGRESSION: phase update not found in cmd_merge"
        )
        assert phase_in_merge > remove_in_merge, (
            "BUG-066 REGRESSION: Phase update must happen AFTER worktree removal, "
            "not before, to avoid partial state if removal fails."
        )

    def test_current_phase_is_captured_for_logging(self) -> None:
        """Verify current phase is captured before update for logging.

        To log 'X -> Y' transition, we need to capture the current phase
        before updating it.
        """
        source = self.get_claws_worktree_script()

        # Should have a variable capturing current/old phase
        assert re.search(r'current_phase|old_phase', source, re.IGNORECASE), (
            "BUG-066 REGRESSION: Should capture current phase before update "
            "to enable logging 'old -> new' transition."
        )
