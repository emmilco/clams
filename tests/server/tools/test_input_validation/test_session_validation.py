"""Input validation tests for session tools.

Tests cover:
- start_session: (no validation needed - takes no parameters)
- get_orphaned_ghap: (no validation needed - takes no parameters)
- should_check_in: frequency (SPEC-057: range validation 1-1000)
- increment_tool_count: (no validation needed - takes no parameters)
- reset_tool_count: (no validation needed - takes no parameters)

Note: Session tools have minimal validation requirements as most take no
parameters or have sensible defaults.
"""

import re
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
        """SPEC-057: Zero frequency should error.

        Frequency must be in range 1-1000.
        """
        tool = session_tools["should_check_in"]
        result = await tool(frequency=0)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"between 1 and 1000", result["error"]["message"])
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


# ============================================================================
# SPEC-057: New validation tests
# ============================================================================


class TestShouldCheckInFrequencyValidation:
    """SPEC-057: Frequency range validation tests for should_check_in."""

    @pytest.mark.asyncio
    async def test_frequency_below_range(
        self, session_tools: dict[str, Any]
    ) -> None:
        """Frequency < 1 should error."""
        tool = session_tools["should_check_in"]
        result = await tool(frequency=0)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"between 1 and 1000", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_frequency_negative(
        self, session_tools: dict[str, Any]
    ) -> None:
        """Negative frequency should error."""
        tool = session_tools["should_check_in"]
        result = await tool(frequency=-1)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"between 1 and 1000", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_frequency_above_range(
        self, session_tools: dict[str, Any]
    ) -> None:
        """Frequency > 1000 should error."""
        tool = session_tools["should_check_in"]
        result = await tool(frequency=1001)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"between 1 and 1000", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_frequency_at_boundary_lower(
        self, session_tools: dict[str, Any]
    ) -> None:
        """Frequency = 1 should be accepted."""
        tool = session_tools["should_check_in"]
        result = await tool(frequency=1)
        assert "should_check_in" in result

    @pytest.mark.asyncio
    async def test_frequency_at_boundary_upper(
        self, session_tools: dict[str, Any]
    ) -> None:
        """Frequency = 1000 should be accepted."""
        tool = session_tools["should_check_in"]
        result = await tool(frequency=1000)
        assert "should_check_in" in result

    @pytest.mark.asyncio
    async def test_frequency_error_shows_range(
        self, session_tools: dict[str, Any]
    ) -> None:
        """Error should show the valid range."""
        tool = session_tools["should_check_in"]
        result = await tool(frequency=0)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "1" in result["error"]["message"]
