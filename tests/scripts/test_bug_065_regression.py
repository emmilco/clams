"""Regression test for BUG-065: Add next-commands to handoff format.

This test verifies that:
1. claws-session has get_next_action and generate_next_commands functions
2. The next-commands subcommand is available
3. Phase-to-action mapping is correct for both bugs and features
4. claws-status displays next commands when showing handoffs
"""

from pathlib import Path


class TestBug065Regression:
    """Tests for BUG-065 fix: next-commands in handoff format."""

    def get_claws_session_source(self) -> str:
        """Get the source code of claws-session script."""
        scripts_dir = Path(__file__).parent.parent.parent / ".claude" / "bin"
        claws_session_path = scripts_dir / "claws-session"
        return claws_session_path.read_text()

    def get_claws_status_source(self) -> str:
        """Get the source code of claws-status script."""
        scripts_dir = Path(__file__).parent.parent.parent / ".claude" / "bin"
        claws_status_path = scripts_dir / "claws-status"
        return claws_status_path.read_text()

    def test_get_next_action_function_exists(self) -> None:
        """Verify get_next_action function is defined in claws-session."""
        source = self.get_claws_session_source()

        assert "get_next_action()" in source, (
            "BUG-065 REGRESSION: get_next_action function not found in claws-session"
        )

    def test_describe_next_action_function_exists(self) -> None:
        """Verify describe_next_action function is defined in claws-session."""
        source = self.get_claws_session_source()

        assert "describe_next_action()" in source, (
            "BUG-065 REGRESSION: describe_next_action function not found in claws-session"
        )

    def test_generate_next_commands_function_exists(self) -> None:
        """Verify generate_next_commands function is defined in claws-session."""
        source = self.get_claws_session_source()

        assert "generate_next_commands()" in source, (
            "BUG-065 REGRESSION: generate_next_commands function not found in claws-session"
        )

    def test_next_commands_subcommand_in_case_statement(self) -> None:
        """Verify next-commands is handled in the case statement."""
        source = self.get_claws_session_source()

        assert "next-commands)" in source, (
            "BUG-065 REGRESSION: next-commands case not found in claws-session"
        )

    def test_next_commands_in_usage(self) -> None:
        """Verify next-commands is documented in usage output."""
        source = self.get_claws_session_source()

        assert "claws-session next-commands" in source, (
            "BUG-065 REGRESSION: next-commands not documented in claws-session usage"
        )

    def test_bug_phases_have_actions(self) -> None:
        """Verify all bug phases have corresponding actions in get_next_action."""
        source = self.get_claws_session_source()

        bug_phases = [
            "REPORTED",
            "INVESTIGATED",
            "FIXED",
            "REVIEWED",
            "TESTED",
            "MERGED",
            "DONE",
        ]

        for phase in bug_phases:
            # Look for the phase in get_next_action's case statement for bugs
            assert f"{phase})" in source, (
                f"BUG-065 REGRESSION: Bug phase {phase} not handled in get_next_action"
            )

    def test_feature_phases_have_actions(self) -> None:
        """Verify all feature phases have corresponding actions in get_next_action."""
        source = self.get_claws_session_source()

        feature_phases = [
            "SPEC",
            "DESIGN",
            "IMPLEMENT",
            "CODE_REVIEW",
            "TEST",
            "INTEGRATE",
            "VERIFY",
            "DONE",
        ]

        for phase in feature_phases:
            # Look for the phase in get_next_action's case statement
            assert f"{phase})" in source, (
                f"BUG-065 REGRESSION: Feature phase {phase} not handled in get_next_action"
            )

    def test_investigated_phase_has_gate_check(self) -> None:
        """Verify INVESTIGATED phase maps to gate check command."""
        source = self.get_claws_session_source()

        # Look for the INVESTIGATED-FIXED gate check
        assert "INVESTIGATED-FIXED" in source, (
            "BUG-065 REGRESSION: INVESTIGATED phase should trigger INVESTIGATED-FIXED gate check"
        )

    def test_implement_phase_has_gate_check(self) -> None:
        """Verify IMPLEMENT phase maps to gate check command."""
        source = self.get_claws_session_source()

        # Look for the IMPLEMENT-CODE_REVIEW gate check
        assert "IMPLEMENT-CODE_REVIEW" in source, (
            "BUG-065 REGRESSION: IMPLEMENT phase should trigger IMPLEMENT-CODE_REVIEW gate check"
        )

    def test_merge_command_for_integrate_phase(self) -> None:
        """Verify INTEGRATE phase maps to merge command."""
        source = self.get_claws_session_source()

        # Look for claws-worktree merge in the context of INTEGRATE phase
        assert "claws-worktree merge" in source, (
            "BUG-065 REGRESSION: INTEGRATE phase should trigger worktree merge command"
        )

    def test_claws_status_calls_next_commands(self) -> None:
        """Verify claws-status displays next commands when showing handoffs."""
        source = self.get_claws_status_source()

        # Check that claws-status calls claws-session next-commands
        assert "claws-session" in source and "next-commands" in source, (
            "BUG-065 REGRESSION: claws-status should call claws-session next-commands for handoffs"
        )

    def test_next_commands_displayed_prominently(self) -> None:
        """Verify next commands section has a prominent header in claws-status."""
        source = self.get_claws_status_source()

        # Check for prominent header
        assert "Next Commands" in source, (
            "BUG-065 REGRESSION: claws-status should display 'Next Commands' header"
        )

    def test_pending_actions_section_exists(self) -> None:
        """Verify generate_next_commands outputs a Pending Actions section."""
        source = self.get_claws_session_source()

        assert "Pending Actions" in source, (
            "BUG-065 REGRESSION: generate_next_commands should output 'Pending Actions' section"
        )

    def test_code_block_in_next_commands(self) -> None:
        """Verify generate_next_commands outputs commands in a code block."""
        source = self.get_claws_session_source()

        # Check for markdown code block markers
        assert '```bash' in source or "```" in source, (
            "BUG-065 REGRESSION: generate_next_commands should output commands in code block"
        )

    def test_task_show_command_included(self) -> None:
        """Verify generate_next_commands includes task show command."""
        source = self.get_claws_session_source()

        assert "claws-task show" in source, (
            "BUG-065 REGRESSION: generate_next_commands should include claws-task show command"
        )
