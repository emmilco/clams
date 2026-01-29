"""Input validation tests for search tools.

Tests cover:
- search_experiences: query, axis, domain, outcome, limit

This test module verifies that all validation constraints are enforced
with informative error messages.
"""

from typing import Any

import pytest

from .helpers import assert_error_response


class TestSearchExperiencesValidation:
    """Validation tests for search_experiences tool."""

    @pytest.mark.asyncio
    async def test_search_experiences_missing_query(
        self, search_tools: dict[str, Any]
    ) -> None:
        """Test that search_experiences requires query field."""
        tool = search_tools["search_experiences"]
        with pytest.raises(TypeError, match="query"):
            await tool()

    @pytest.mark.asyncio
    async def test_search_experiences_empty_query_returns_empty(
        self, search_tools: dict[str, Any]
    ) -> None:
        """Test that search_experiences returns empty for empty query."""
        tool = search_tools["search_experiences"]
        result = await tool(query="")
        assert result["count"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_search_experiences_whitespace_query_returns_empty(
        self, search_tools: dict[str, Any]
    ) -> None:
        """Test that search_experiences returns empty for whitespace query."""
        tool = search_tools["search_experiences"]
        result = await tool(query="   ")
        assert result["count"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_search_experiences_invalid_axis(
        self, search_tools: dict[str, Any]
    ) -> None:
        """Test that search_experiences rejects invalid axis."""
        tool = search_tools["search_experiences"]
        result = await tool(query="test", axis="invalid")
        assert_error_response(result, field_name="axis")

    @pytest.mark.asyncio
    async def test_search_experiences_invalid_axis_lists_valid_options(
        self, search_tools: dict[str, Any]
    ) -> None:
        """Test that axis error lists valid options."""
        tool = search_tools["search_experiences"]
        result = await tool(query="test", axis="invalid")
        assert "full" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_search_experiences_invalid_domain(
        self, search_tools: dict[str, Any]
    ) -> None:
        """Test that search_experiences rejects invalid domain."""
        tool = search_tools["search_experiences"]
        result = await tool(query="test", domain="invalid")
        assert_error_response(result, field_name="domain")

    @pytest.mark.asyncio
    async def test_search_experiences_invalid_outcome(
        self, search_tools: dict[str, Any]
    ) -> None:
        """Test that search_experiences rejects invalid outcome."""
        tool = search_tools["search_experiences"]
        result = await tool(query="test", outcome="invalid")
        assert_error_response(result, message_contains="outcome status")

    @pytest.mark.asyncio
    async def test_search_experiences_limit_below_range(
        self, search_tools: dict[str, Any]
    ) -> None:
        """Test that search_experiences rejects limit < 1."""
        tool = search_tools["search_experiences"]
        result = await tool(query="test", limit=0)
        assert_error_response(result, message_contains="between 1 and 50")

    @pytest.mark.asyncio
    async def test_search_experiences_limit_above_range(
        self, search_tools: dict[str, Any]
    ) -> None:
        """Test that search_experiences rejects limit > 50."""
        tool = search_tools["search_experiences"]
        result = await tool(query="test", limit=51)
        assert_error_response(result, message_contains="between 1 and 50")

    @pytest.mark.asyncio
    async def test_search_experiences_limit_negative(
        self, search_tools: dict[str, Any]
    ) -> None:
        """Test that search_experiences rejects negative limit."""
        tool = search_tools["search_experiences"]
        result = await tool(query="test", limit=-1)
        assert_error_response(result, message_contains="between 1 and 50")

    @pytest.mark.asyncio
    async def test_search_experiences_limit_at_boundary_lower(
        self, search_tools: dict[str, Any], mock_searcher: Any
    ) -> None:
        """Test that search_experiences accepts limit = 1."""
        tool = search_tools["search_experiences"]
        result = await tool(query="test", limit=1)
        # Should not fail validation
        if "error" in result:
            assert result["error"]["type"] != "validation_error"

    @pytest.mark.asyncio
    async def test_search_experiences_limit_at_boundary_upper(
        self, search_tools: dict[str, Any], mock_searcher: Any
    ) -> None:
        """Test that search_experiences accepts limit = 50."""
        tool = search_tools["search_experiences"]
        result = await tool(query="test", limit=50)
        if "error" in result:
            assert result["error"]["type"] != "validation_error"


class TestAllValidEnumsAccepted:
    """Test that all documented enum values are accepted."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("axis", ["full", "strategy", "surprise", "root_cause"])
    async def test_search_experiences_accepts_valid_axis(
        self, search_tools: dict[str, Any], mock_searcher: Any, axis: str
    ) -> None:
        """Test that search_experiences accepts all valid axis values."""
        tool = search_tools["search_experiences"]
        result = await tool(query="test", axis=axis)
        if "error" in result:
            assert result["error"]["type"] != "validation_error"

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
    async def test_search_experiences_accepts_valid_domain(
        self, search_tools: dict[str, Any], mock_searcher: Any, domain: str
    ) -> None:
        """Test that search_experiences accepts all valid domain values."""
        tool = search_tools["search_experiences"]
        result = await tool(query="test", domain=domain)
        if "error" in result:
            assert result["error"]["type"] != "validation_error"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("outcome", ["confirmed", "falsified", "abandoned"])
    async def test_search_experiences_accepts_valid_outcome(
        self, search_tools: dict[str, Any], mock_searcher: Any, outcome: str
    ) -> None:
        """Test that search_experiences accepts all valid outcome values."""
        tool = search_tools["search_experiences"]
        result = await tool(query="test", outcome=outcome)
        if "error" in result:
            assert result["error"]["type"] != "validation_error"


# ============================================================================
# SPEC-057: New validation tests
# ============================================================================


class TestSearchExperiencesQueryLengthValidation:
    """SPEC-057: Query string length validation tests for search_experiences."""

    @pytest.mark.asyncio
    async def test_query_too_long(self, search_tools: dict[str, Any]) -> None:
        """Query exceeding 10,000 chars should error."""
        tool = search_tools["search_experiences"]
        result = await tool(query="x" * 10_001)
        assert_error_response(result, message_contains="too long")

    @pytest.mark.asyncio
    async def test_query_at_max_length(
        self, search_tools: dict[str, Any], mock_searcher: Any
    ) -> None:
        """Query at exactly 10,000 chars should be accepted."""
        tool = search_tools["search_experiences"]
        result = await tool(query="x" * 10_000)
        # Should not fail with validation error
        if "error" in result:
            assert "too long" not in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_query_length_error_shows_limits(
        self, search_tools: dict[str, Any]
    ) -> None:
        """Error should show actual and maximum length."""
        tool = search_tools["search_experiences"]
        result = await tool(query="x" * 10_001)
        assert "10001" in result["error"]["message"]
        assert "10000" in result["error"]["message"]
