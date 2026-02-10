"""Input validation tests for context tools.

Tests cover:
- assemble_context: query, context_types, limit, max_tokens

SPEC-057 additions:
- Invalid context_type should error, not silently ignore
- Limit range validation (1-50)
- Max_tokens range validation (100-10000)
- Empty query returns empty result gracefully
"""

import re
from typing import Any

import pytest


class TestAssembleContextValidation:
    """Validation tests for assemble_context tool."""

    @pytest.mark.asyncio
    async def test_assemble_context_missing_query(
        self, context_tools: dict[str, Any]
    ) -> None:
        """Test that assemble_context requires query field."""
        tool = context_tools["assemble_context"]
        with pytest.raises(TypeError, match="query"):
            await tool()

    @pytest.mark.asyncio
    async def test_assemble_context_empty_query(
        self, context_tools: dict[str, Any]
    ) -> None:
        """Test that assemble_context handles empty query.

        Note: Empty query is accepted, returns minimal context.
        """
        tool = context_tools["assemble_context"]
        result = await tool(query="")
        assert "markdown" in result
        assert "token_count" in result
        assert "item_count" in result

    @pytest.mark.asyncio
    async def test_assemble_context_default_context_types(
        self, context_tools: dict[str, Any]
    ) -> None:
        """Test that assemble_context uses default context_types."""
        tool = context_tools["assemble_context"]
        result = await tool(query="test")
        assert "markdown" in result
        # Default includes both values and experiences

    @pytest.mark.asyncio
    async def test_assemble_context_custom_context_types(
        self, context_tools: dict[str, Any]
    ) -> None:
        """Test that assemble_context accepts custom context_types."""
        tool = context_tools["assemble_context"]
        result = await tool(query="test", context_types=["values"])
        assert "markdown" in result

    @pytest.mark.asyncio
    async def test_assemble_context_empty_context_types(
        self, context_tools: dict[str, Any]
    ) -> None:
        """Test that assemble_context handles empty context_types list."""
        tool = context_tools["assemble_context"]
        result = await tool(query="test", context_types=[])
        assert "markdown" in result
        # With no context types, should return empty markdown
        assert result["item_count"] == 0

    @pytest.mark.asyncio
    async def test_assemble_context_invalid_context_type(
        self, context_tools: dict[str, Any]
    ) -> None:
        """Test that assemble_context rejects invalid context_type.

        SPEC-057: Invalid context_type should error, not silently ignore.
        """
        tool = context_tools["assemble_context"]
        result = await tool(query="test", context_types=["invalid"])
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Invalid context types", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_assemble_context_invalid_context_type_lists_valid_options(
        self, context_tools: dict[str, Any]
    ) -> None:
        """Test that error message lists valid options."""
        tool = context_tools["assemble_context"]
        result = await tool(query="test", context_types=["wrong"])
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "values" in result["error"]["message"]
    @pytest.mark.asyncio
    async def test_assemble_context_custom_limit(
        self, context_tools: dict[str, Any]
    ) -> None:
        """Test that assemble_context accepts custom limit."""
        tool = context_tools["assemble_context"]
        result = await tool(query="test", limit=5)
        assert "markdown" in result

    @pytest.mark.asyncio
    async def test_assemble_context_custom_max_tokens(
        self, context_tools: dict[str, Any]
    ) -> None:
        """Test that assemble_context accepts custom max_tokens."""
        tool = context_tools["assemble_context"]
        result = await tool(query="test", max_tokens=500)
        assert "markdown" in result
        assert "truncated" in result


class TestAssembleContextLimitValidation:
    """SPEC-057: Limit range validation tests."""

    @pytest.mark.asyncio
    async def test_limit_below_range(self, context_tools: dict[str, Any]) -> None:
        """limit=0 should error."""
        tool = context_tools["assemble_context"]
        result = await tool(query="test", limit=0)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Limit.*out of range", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_limit_above_range(self, context_tools: dict[str, Any]) -> None:
        """limit=100 should error (max is 50)."""
        tool = context_tools["assemble_context"]
        result = await tool(query="test", limit=100)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Limit.*out of range", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_limit_at_boundary_lower(
        self, context_tools: dict[str, Any]
    ) -> None:
        """limit=1 should be accepted."""
        tool = context_tools["assemble_context"]
        result = await tool(query="test", limit=1)
        assert "markdown" in result

    @pytest.mark.asyncio
    async def test_limit_at_boundary_upper(
        self, context_tools: dict[str, Any]
    ) -> None:
        """limit=50 should be accepted."""
        tool = context_tools["assemble_context"]
        result = await tool(query="test", limit=50)
        assert "markdown" in result


class TestAssembleContextMaxTokensValidation:
    """SPEC-057: max_tokens range validation tests."""

    @pytest.mark.asyncio
    async def test_max_tokens_below_range(
        self, context_tools: dict[str, Any]
    ) -> None:
        """max_tokens=50 should error (min is 100)."""
        tool = context_tools["assemble_context"]
        result = await tool(query="test", max_tokens=50)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Max_tokens.*out of range", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_max_tokens_above_range(
        self, context_tools: dict[str, Any]
    ) -> None:
        """max_tokens=20000 should error (max is 10000)."""
        tool = context_tools["assemble_context"]
        result = await tool(query="test", max_tokens=20000)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Max_tokens.*out of range", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_max_tokens_at_boundary_lower(
        self, context_tools: dict[str, Any]
    ) -> None:
        """max_tokens=100 should be accepted."""
        tool = context_tools["assemble_context"]
        result = await tool(query="test", max_tokens=100)
        assert "markdown" in result

    @pytest.mark.asyncio
    async def test_max_tokens_at_boundary_upper(
        self, context_tools: dict[str, Any]
    ) -> None:
        """max_tokens=10000 should be accepted."""
        tool = context_tools["assemble_context"]
        result = await tool(query="test", max_tokens=10000)
        assert "markdown" in result


class TestAssembleContextEmptyQuery:
    """SPEC-057: Empty query handling tests."""

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty_result(
        self, context_tools: dict[str, Any]
    ) -> None:
        """Empty query should return empty result, not error."""
        tool = context_tools["assemble_context"]
        result = await tool(query="")
        assert result["item_count"] == 0
        assert result["markdown"] == ""
        assert result["token_count"] == 0
        assert result["truncated"] is False

    @pytest.mark.asyncio
    async def test_whitespace_query_returns_empty_result(
        self, context_tools: dict[str, Any]
    ) -> None:
        """Whitespace-only query should return empty result, not error."""
        tool = context_tools["assemble_context"]
        result = await tool(query="   ")
        assert result["item_count"] == 0
        assert result["markdown"] == ""


class TestAssembleContextIntegration:
    """Integration tests for assemble_context validation behavior."""

    @pytest.mark.asyncio
    async def test_assemble_context_returns_truncated_flag(
        self, context_tools: dict[str, Any]
    ) -> None:
        """Test that assemble_context returns truncated flag correctly."""
        tool = context_tools["assemble_context"]
        # With valid max_tokens in range, check truncated flag
        result = await tool(query="test", max_tokens=100)
        assert "truncated" in result
        # Truncated is True if token_count > max_tokens

    @pytest.mark.asyncio
    async def test_assemble_context_returns_all_fields(
        self, context_tools: dict[str, Any]
    ) -> None:
        """Test that assemble_context returns all expected fields."""
        tool = context_tools["assemble_context"]
        result = await tool(query="test")
        assert "markdown" in result
        assert "token_count" in result
        assert "item_count" in result
        assert "truncated" in result


# ============================================================================
# SPEC-057: New validation tests
# ============================================================================


class TestAssembleContextQueryLengthValidation:
    """SPEC-057: Query string length validation tests for assemble_context."""

    @pytest.mark.asyncio
    async def test_query_too_long(self, context_tools: dict[str, Any]) -> None:
        """Query exceeding 10,000 chars should error."""
        tool = context_tools["assemble_context"]
        result = await tool(query="x" * 10_001)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"too long", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_query_at_max_length(
        self, context_tools: dict[str, Any]
    ) -> None:
        """Query at exactly 10,000 chars should be accepted."""
        tool = context_tools["assemble_context"]
        # Should not raise ValidationError
        result = await tool(query="x" * 10_000)
        # Valid query should return result structure
        assert "markdown" in result

    @pytest.mark.asyncio
    async def test_query_length_error_shows_limits(
        self, context_tools: dict[str, Any]
    ) -> None:
        """Error should show actual and maximum length."""
        tool = context_tools["assemble_context"]
        result = await tool(query="x" * 10_001)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "10001" in result["error"]["message"]
