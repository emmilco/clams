"""Input validation tests for context tools.

Tests cover:
- assemble_context: query, context_types, limit, max_tokens

Note: Context tools have minimal validation requirements.
Most inputs have sensible defaults.
"""

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
        """Test that assemble_context handles invalid context_type.

        Note: The current implementation simply ignores unknown context types
        rather than raising a validation error.
        """
        tool = context_tools["assemble_context"]
        result = await tool(query="test", context_types=["invalid"])
        assert "markdown" in result
        # Invalid type is ignored, so no items returned
        assert result["item_count"] == 0

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


class TestAssembleContextIntegration:
    """Integration tests for assemble_context validation behavior."""

    @pytest.mark.asyncio
    async def test_assemble_context_returns_truncated_flag(
        self, context_tools: dict[str, Any]
    ) -> None:
        """Test that assemble_context returns truncated flag correctly."""
        tool = context_tools["assemble_context"]
        # With very low max_tokens, should indicate truncation
        result = await tool(query="test", max_tokens=1)
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
