"""Input validation tests for session tools.

Tests cover:
- start_session: (no validation needed - takes no parameters)
- get_orphaned_ghap: (no validation needed - takes no parameters)
- should_check_in: frequency
- increment_tool_count: (no validation needed - takes no parameters)
- reset_tool_count: (no validation needed - takes no parameters)

Note: Session tools have minimal validation requirements as most take no
parameters or have sensible defaults.
"""

from typing import Any

import pytest


class TestStartSessionValidation:
    """Validation tests for start_session tool."""

    @pytest.mark.asyncio
    async def test_start_session_no_parameters_required(
        self, session_tools: dict[str, Any]
    ) -> None:
        """Test that start_session works with no parameters."""
        tool = session_tools["start_session"]
        result = await tool()
        assert "session_id" in result
        assert "started_at" in result


class TestGetOrphanedGhapValidation:
    """Validation tests for get_orphaned_ghap tool."""

    @pytest.mark.asyncio
    async def test_get_orphaned_ghap_no_parameters_required(
        self, session_tools: dict[str, Any]
    ) -> None:
        """Test that get_orphaned_ghap works with no parameters."""
        tool = session_tools["get_orphaned_ghap"]
        result = await tool()
        assert "has_orphan" in result


class TestShouldCheckInValidation:
    """Validation tests for should_check_in tool."""

    @pytest.mark.asyncio
    async def test_should_check_in_default_frequency(
        self, session_tools: dict[str, Any]
    ) -> None:
        """Test that should_check_in works with default frequency."""
        tool = session_tools["should_check_in"]
        result = await tool()
        assert "should_check_in" in result

    @pytest.mark.asyncio
    async def test_should_check_in_custom_frequency(
        self, session_tools: dict[str, Any]
    ) -> None:
        """Test that should_check_in accepts custom frequency."""
        tool = session_tools["should_check_in"]
        result = await tool(frequency=5)
        assert "should_check_in" in result

    @pytest.mark.asyncio
    async def test_should_check_in_zero_frequency(
        self, session_tools: dict[str, Any]
    ) -> None:
        """Test that should_check_in handles zero frequency.

        Note: The implementation doesn't validate frequency bounds,
        so zero is accepted (returns True since tool_count >= 0).
        """
        tool = session_tools["should_check_in"]
        result = await tool(frequency=0)
        assert "should_check_in" in result
        # With 0 tool count and 0 frequency, should be True
        assert result["should_check_in"] is True


class TestIncrementToolCountValidation:
    """Validation tests for increment_tool_count tool."""

    @pytest.mark.asyncio
    async def test_increment_tool_count_no_parameters_required(
        self, session_tools: dict[str, Any]
    ) -> None:
        """Test that increment_tool_count works with no parameters."""
        tool = session_tools["increment_tool_count"]
        result = await tool()
        assert "tool_count" in result


class TestResetToolCountValidation:
    """Validation tests for reset_tool_count tool."""

    @pytest.mark.asyncio
    async def test_reset_tool_count_no_parameters_required(
        self, session_tools: dict[str, Any]
    ) -> None:
        """Test that reset_tool_count works with no parameters."""
        tool = session_tools["reset_tool_count"]
        result = await tool()
        assert "tool_count" in result
        assert result["tool_count"] == 0
