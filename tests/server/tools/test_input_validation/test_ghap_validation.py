"""Input validation tests for GHAP tools.

Tests cover:
- start_ghap: domain, strategy, goal, hypothesis, action, prediction
- update_ghap: hypothesis, action, prediction, strategy, note
- resolve_ghap: status, result, surprise, root_cause, lesson
- get_active_ghap: (no validation needed)
- list_ghap_entries: limit, domain, outcome, since

SPEC-057 additions:
- update_ghap: note max length validation (2000 chars)

This test module verifies that all validation constraints are enforced
with informative error messages.

References bugs:
- BUG-024: Error message mismatch between stores
"""

from typing import Any

import pytest

from .helpers import assert_error_response


class TestStartGhapValidation:
    """Validation tests for start_ghap tool."""

    @pytest.mark.asyncio
    async def test_start_ghap_missing_domain(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that start_ghap requires domain field."""
        tool = ghap_tools["start_ghap"]
        with pytest.raises(TypeError, match="domain"):
            await tool(
                strategy="systematic-elimination",
                goal="Test",
                hypothesis="Test",
                action="Test",
                prediction="Test",
            )

    @pytest.mark.asyncio
    async def test_start_ghap_missing_strategy(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that start_ghap requires strategy field."""
        tool = ghap_tools["start_ghap"]
        with pytest.raises(TypeError, match="strategy"):
            await tool(
                domain="debugging",
                goal="Test",
                hypothesis="Test",
                action="Test",
                prediction="Test",
            )

    @pytest.mark.asyncio
    async def test_start_ghap_missing_goal(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that start_ghap requires goal field."""
        tool = ghap_tools["start_ghap"]
        with pytest.raises(TypeError, match="goal"):
            await tool(
                domain="debugging",
                strategy="systematic-elimination",
                hypothesis="Test",
                action="Test",
                prediction="Test",
            )

    @pytest.mark.asyncio
    async def test_start_ghap_missing_hypothesis(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that start_ghap requires hypothesis field."""
        tool = ghap_tools["start_ghap"]
        with pytest.raises(TypeError, match="hypothesis"):
            await tool(
                domain="debugging",
                strategy="systematic-elimination",
                goal="Test",
                action="Test",
                prediction="Test",
            )

    @pytest.mark.asyncio
    async def test_start_ghap_missing_action(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that start_ghap requires action field."""
        tool = ghap_tools["start_ghap"]
        with pytest.raises(TypeError, match="action"):
            await tool(
                domain="debugging",
                strategy="systematic-elimination",
                goal="Test",
                hypothesis="Test",
                prediction="Test",
            )

    @pytest.mark.asyncio
    async def test_start_ghap_missing_prediction(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that start_ghap requires prediction field."""
        tool = ghap_tools["start_ghap"]
        with pytest.raises(TypeError, match="prediction"):
            await tool(
                domain="debugging",
                strategy="systematic-elimination",
                goal="Test",
                hypothesis="Test",
                action="Test",
            )

    @pytest.mark.asyncio
    async def test_start_ghap_invalid_domain(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that start_ghap rejects invalid domain."""
        tool = ghap_tools["start_ghap"]
        result = await tool(
            domain="invalid",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )
        assert_error_response(result, field_name="domain")

    @pytest.mark.asyncio
    async def test_start_ghap_invalid_domain_lists_valid_options(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that domain error lists valid options."""
        tool = ghap_tools["start_ghap"]
        result = await tool(
            domain="invalid",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )
        assert "debugging" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_start_ghap_invalid_strategy(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that start_ghap rejects invalid strategy."""
        tool = ghap_tools["start_ghap"]
        result = await tool(
            domain="debugging",
            strategy="invalid",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )
        assert_error_response(result, field_name="strategy")

    @pytest.mark.asyncio
    async def test_start_ghap_goal_empty(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that start_ghap rejects empty goal."""
        tool = ghap_tools["start_ghap"]
        result = await tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )
        assert_error_response(result, message_contains="cannot be empty")

    @pytest.mark.asyncio
    async def test_start_ghap_goal_whitespace(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that start_ghap rejects whitespace-only goal."""
        tool = ghap_tools["start_ghap"]
        result = await tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="   ",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )
        assert_error_response(result, message_contains="cannot be empty")

    @pytest.mark.asyncio
    async def test_start_ghap_hypothesis_empty(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that start_ghap rejects empty hypothesis."""
        tool = ghap_tools["start_ghap"]
        result = await tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="",
            action="Test",
            prediction="Test",
        )
        assert_error_response(result, message_contains="cannot be empty")

    @pytest.mark.asyncio
    async def test_start_ghap_action_empty(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that start_ghap rejects empty action."""
        tool = ghap_tools["start_ghap"]
        result = await tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="",
            prediction="Test",
        )
        assert_error_response(result, message_contains="cannot be empty")

    @pytest.mark.asyncio
    async def test_start_ghap_prediction_empty(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that start_ghap rejects empty prediction."""
        tool = ghap_tools["start_ghap"]
        result = await tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="",
        )
        assert_error_response(result, message_contains="cannot be empty")

    @pytest.mark.asyncio
    async def test_start_ghap_goal_too_long(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that start_ghap rejects goal exceeding 1000 chars."""
        tool = ghap_tools["start_ghap"]
        result = await tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="x" * 1001,
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )
        assert_error_response(result, message_contains="1000 character limit")

    @pytest.mark.asyncio
    async def test_start_ghap_hypothesis_too_long(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that start_ghap rejects hypothesis exceeding 1000 chars."""
        tool = ghap_tools["start_ghap"]
        result = await tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="x" * 1001,
            action="Test",
            prediction="Test",
        )
        assert_error_response(result, message_contains="1000 character limit")

    @pytest.mark.asyncio
    async def test_start_ghap_action_too_long(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that start_ghap rejects action exceeding 1000 chars."""
        tool = ghap_tools["start_ghap"]
        result = await tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="x" * 1001,
            prediction="Test",
        )
        assert_error_response(result, message_contains="1000 character limit")

    @pytest.mark.asyncio
    async def test_start_ghap_prediction_too_long(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that start_ghap rejects prediction exceeding 1000 chars."""
        tool = ghap_tools["start_ghap"]
        result = await tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="x" * 1001,
        )
        assert_error_response(result, message_contains="1000 character limit")


class TestUpdateGhapValidation:
    """Validation tests for update_ghap tool."""

    @pytest.mark.asyncio
    async def test_update_ghap_no_active_entry(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that update_ghap fails when no active GHAP exists."""
        tool = ghap_tools["update_ghap"]
        result = await tool(hypothesis="Updated")
        assert_error_response(result, error_type="not_found")

    @pytest.mark.asyncio
    async def test_update_ghap_invalid_strategy(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that update_ghap rejects invalid strategy."""
        # First start a GHAP
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        # Try to update with invalid strategy
        tool = ghap_tools["update_ghap"]
        result = await tool(strategy="invalid")
        assert_error_response(result, field_name="strategy")

    @pytest.mark.asyncio
    async def test_update_ghap_hypothesis_too_long(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that update_ghap rejects hypothesis exceeding 1000 chars."""
        # First start a GHAP
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        # Try to update with too-long hypothesis
        tool = ghap_tools["update_ghap"]
        result = await tool(hypothesis="x" * 1001)
        assert_error_response(result, message_contains="1000 character limit")

    @pytest.mark.asyncio
    async def test_update_ghap_note_too_long(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """SPEC-057: Note > 2000 chars should error."""
        # First start a GHAP
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        # Try to update with too-long note
        tool = ghap_tools["update_ghap"]
        result = await tool(note="x" * 2001)
        assert_error_response(result, message_contains="2000")

    @pytest.mark.asyncio
    async def test_update_ghap_note_at_limit_accepted(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """SPEC-057: Note of exactly 2000 chars should be accepted."""
        # First start a GHAP
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        # Update with note at limit
        tool = ghap_tools["update_ghap"]
        result = await tool(note="x" * 2000)
        # Should succeed (have success or no error)
        assert "success" in result or "error" not in result


class TestResolveGhapValidation:
    """Validation tests for resolve_ghap tool."""

    @pytest.mark.asyncio
    async def test_resolve_ghap_missing_status(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that resolve_ghap requires status field."""
        tool = ghap_tools["resolve_ghap"]
        with pytest.raises(TypeError, match="status"):
            await tool(result="Test result")

    @pytest.mark.asyncio
    async def test_resolve_ghap_missing_result(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that resolve_ghap requires result field."""
        tool = ghap_tools["resolve_ghap"]
        with pytest.raises(TypeError, match="result"):
            await tool(status="confirmed")

    @pytest.mark.asyncio
    async def test_resolve_ghap_invalid_status(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that resolve_ghap rejects invalid status."""
        # First start a GHAP
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        tool = ghap_tools["resolve_ghap"]
        result = await tool(status="invalid", result="Test")
        assert_error_response(result, message_contains="outcome status")

    @pytest.mark.asyncio
    async def test_resolve_ghap_invalid_status_lists_valid_options(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that status error lists valid options."""
        # First start a GHAP
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        tool = ghap_tools["resolve_ghap"]
        result = await tool(status="invalid", result="Test")
        # Should list confirmed, falsified, abandoned
        assert "confirmed" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_resolve_ghap_result_too_long(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that resolve_ghap rejects result exceeding 2000 chars."""
        # First start a GHAP
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        tool = ghap_tools["resolve_ghap"]
        result = await tool(status="confirmed", result="x" * 2001)
        assert_error_response(result, message_contains="2000 character limit")

    @pytest.mark.asyncio
    async def test_resolve_ghap_falsified_missing_surprise(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that resolve_ghap requires surprise when status=falsified."""
        # First start a GHAP
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        tool = ghap_tools["resolve_ghap"]
        result = await tool(status="falsified", result="Test")
        assert_error_response(result, message_contains="surprise")

    @pytest.mark.asyncio
    async def test_resolve_ghap_falsified_missing_root_cause(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that resolve_ghap requires root_cause when status=falsified."""
        # First start a GHAP
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        tool = ghap_tools["resolve_ghap"]
        result = await tool(
            status="falsified",
            result="Test",
            surprise="Unexpected behavior",
        )
        assert_error_response(result, message_contains="root_cause")

    @pytest.mark.asyncio
    async def test_resolve_ghap_root_cause_wrong_type(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that resolve_ghap rejects non-dict root_cause."""
        # First start a GHAP
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        tool = ghap_tools["resolve_ghap"]
        result = await tool(
            status="falsified",
            result="Test",
            surprise="Unexpected",
            root_cause="not a dict",
        )
        assert_error_response(result, message_contains="root_cause")

    @pytest.mark.asyncio
    async def test_resolve_ghap_root_cause_missing_category(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that resolve_ghap requires root_cause.category."""
        # First start a GHAP
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        tool = ghap_tools["resolve_ghap"]
        result = await tool(
            status="falsified",
            result="Test",
            surprise="Unexpected",
            root_cause={"description": "Missing category"},
        )
        assert_error_response(result, message_contains="root_cause.category")

    @pytest.mark.asyncio
    async def test_resolve_ghap_root_cause_missing_description(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that resolve_ghap requires root_cause.description."""
        # First start a GHAP
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        tool = ghap_tools["resolve_ghap"]
        result = await tool(
            status="falsified",
            result="Test",
            surprise="Unexpected",
            root_cause={"category": "wrong-assumption"},
        )
        assert_error_response(result, message_contains="root_cause.description")

    @pytest.mark.asyncio
    async def test_resolve_ghap_root_cause_invalid_category(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that resolve_ghap rejects invalid root_cause.category."""
        # First start a GHAP
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        tool = ghap_tools["resolve_ghap"]
        result = await tool(
            status="falsified",
            result="Test",
            surprise="Unexpected",
            root_cause={"category": "invalid", "description": "Test"},
        )
        assert_error_response(result, message_contains="Invalid root cause category")

    @pytest.mark.asyncio
    async def test_resolve_ghap_lesson_wrong_type(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that resolve_ghap rejects non-dict lesson."""
        # First start a GHAP
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        tool = ghap_tools["resolve_ghap"]
        result = await tool(
            status="confirmed",
            result="Test",
            lesson="not a dict",
        )
        assert_error_response(result, message_contains="lesson")

    @pytest.mark.asyncio
    async def test_resolve_ghap_lesson_missing_what_worked(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that resolve_ghap requires lesson.what_worked when lesson provided."""
        # First start a GHAP
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        tool = ghap_tools["resolve_ghap"]
        result = await tool(
            status="confirmed",
            result="Test",
            lesson={"takeaway": "Missing what_worked"},
        )
        assert_error_response(result, message_contains="lesson.what_worked")

    @pytest.mark.asyncio
    async def test_resolve_ghap_surprise_too_long(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that resolve_ghap rejects surprise exceeding 2000 chars."""
        # First start a GHAP
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        tool = ghap_tools["resolve_ghap"]
        result = await tool(
            status="falsified",
            result="Test",
            surprise="x" * 2001,
            root_cause={"category": "wrong-assumption", "description": "Test"},
        )
        assert_error_response(result, message_contains="2000 character limit")

    @pytest.mark.asyncio
    async def test_resolve_ghap_root_cause_description_too_long(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that resolve_ghap rejects root_cause.description > 2000 chars."""
        # First start a GHAP
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        tool = ghap_tools["resolve_ghap"]
        result = await tool(
            status="falsified",
            result="Test",
            surprise="Test",
            root_cause={"category": "wrong-assumption", "description": "x" * 2001},
        )
        assert_error_response(result, message_contains="2000 character limit")

    @pytest.mark.asyncio
    async def test_resolve_ghap_lesson_what_worked_too_long(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that resolve_ghap rejects lesson.what_worked > 2000 chars."""
        # First start a GHAP
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        tool = ghap_tools["resolve_ghap"]
        result = await tool(
            status="confirmed",
            result="Test",
            lesson={"what_worked": "x" * 2001, "takeaway": "Test"},
        )
        assert_error_response(result, message_contains="2000 character limit")

    @pytest.mark.asyncio
    async def test_resolve_ghap_lesson_takeaway_too_long(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that resolve_ghap rejects lesson.takeaway > 2000 chars."""
        # First start a GHAP
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        tool = ghap_tools["resolve_ghap"]
        result = await tool(
            status="confirmed",
            result="Test",
            lesson={"what_worked": "Test", "takeaway": "x" * 2001},
        )
        assert_error_response(result, message_contains="2000 character limit")


class TestListGhapEntriesValidation:
    """Validation tests for list_ghap_entries tool."""

    @pytest.mark.asyncio
    async def test_list_ghap_entries_limit_below_range(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that list_ghap_entries rejects limit < 1."""
        tool = ghap_tools["list_ghap_entries"]
        result = await tool(limit=0)
        assert_error_response(result, message_contains="between 1 and 100")

    @pytest.mark.asyncio
    async def test_list_ghap_entries_limit_above_range(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that list_ghap_entries rejects limit > 100."""
        tool = ghap_tools["list_ghap_entries"]
        result = await tool(limit=101)
        assert_error_response(result, message_contains="between 1 and 100")

    @pytest.mark.asyncio
    async def test_list_ghap_entries_invalid_domain(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that list_ghap_entries rejects invalid domain."""
        tool = ghap_tools["list_ghap_entries"]
        result = await tool(domain="invalid")
        assert_error_response(result, field_name="domain")

    @pytest.mark.asyncio
    async def test_list_ghap_entries_invalid_outcome(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that list_ghap_entries rejects invalid outcome."""
        tool = ghap_tools["list_ghap_entries"]
        result = await tool(outcome="invalid")
        assert_error_response(result, message_contains="outcome status")

    @pytest.mark.asyncio
    async def test_list_ghap_entries_invalid_since_format(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that list_ghap_entries rejects invalid date format."""
        tool = ghap_tools["list_ghap_entries"]
        result = await tool(since="not-a-date")
        assert_error_response(result, message_contains="Invalid date format")

    @pytest.mark.asyncio
    async def test_list_ghap_entries_valid_since_date(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that list_ghap_entries accepts valid ISO date."""
        tool = ghap_tools["list_ghap_entries"]
        result = await tool(since="2024-01-15T10:30:45+00:00")
        # Should not return error - may return empty results
        assert "error" not in result or result.get("results") is not None

    @pytest.mark.asyncio
    async def test_list_ghap_entries_limit_at_boundary_lower(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that list_ghap_entries accepts limit = 1."""
        tool = ghap_tools["list_ghap_entries"]
        result = await tool(limit=1)
        assert "error" not in result or "results" in result

    @pytest.mark.asyncio
    async def test_list_ghap_entries_limit_at_boundary_upper(
        self, ghap_tools: dict[str, Any]
    ) -> None:
        """Test that list_ghap_entries accepts limit = 100."""
        tool = ghap_tools["list_ghap_entries"]
        result = await tool(limit=100)
        assert "error" not in result or "results" in result


class TestAllValidEnumsAccepted:
    """Test that all documented enum values are accepted."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "domain",
        [
            "debugging",
            "refactoring",
            "feature",
            "testing",
            "configuration",
            "documentation",
            "performance",
            "security",
            "integration",
        ],
    )
    async def test_start_ghap_accepts_valid_domain(
        self, ghap_tools: dict[str, Any], domain: str
    ) -> None:
        """Test that start_ghap accepts all valid domain values."""
        tool = ghap_tools["start_ghap"]
        result = await tool(
            domain=domain,
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )
        assert "error" not in result or result.get("ok") is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "strategy",
        [
            "systematic-elimination",
            "trial-and-error",
            "research-first",
            "divide-and-conquer",
            "root-cause-analysis",
            "copy-from-similar",
            "check-assumptions",
            "read-the-error",
            "ask-user",
        ],
    )
    async def test_start_ghap_accepts_valid_strategy(
        self, ghap_tools: dict[str, Any], strategy: str
    ) -> None:
        """Test that start_ghap accepts all valid strategy values."""
        tool = ghap_tools["start_ghap"]
        result = await tool(
            domain="debugging",
            strategy=strategy,
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )
        # First call succeeds, subsequent may fail due to existing active GHAP
        assert "error" not in result or "active_ghap_exists" in str(result)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status",
        ["confirmed", "falsified", "abandoned"],
    )
    async def test_resolve_ghap_accepts_valid_status(
        self, ghap_tools: dict[str, Any], status: str
    ) -> None:
        """Test that resolve_ghap accepts all valid status values."""
        # Start a GHAP for this test
        start_tool = ghap_tools["start_ghap"]
        await start_tool(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        tool = ghap_tools["resolve_ghap"]

        if status == "falsified":
            result = await tool(
                status=status,
                result="Test",
                surprise="Unexpected",
                root_cause={"category": "wrong-assumption", "description": "Test"},
            )
        else:
            result = await tool(status=status, result="Test")

        # Should not fail validation - may fail for other reasons (no active GHAP)
        if "error" in result:
            assert result["error"]["type"] != "validation_error"
