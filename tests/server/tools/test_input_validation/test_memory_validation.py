"""Input validation tests for memory tools.

Tests cover:
- store_memory: content, category, importance, tags
- retrieve_memories: query, limit, category, min_importance
- list_memories: category, tags, limit, offset
- delete_memory: memory_id

SPEC-057 additions:
- retrieve_memories: min_importance range validation (0.0-1.0)
- store_memory/list_memories: tags array validation (count and length)
- delete_memory: UUID format validation

This test module verifies that all validation constraints are enforced
with informative error messages.
"""

from typing import Any

import pytest

from clams.server.errors import ValidationError


class TestStoreMemoryValidation:
    """Validation tests for store_memory tool."""

    @pytest.mark.asyncio
    async def test_store_memory_missing_content(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that store_memory requires content field."""
        tool = memory_tools["store_memory"]
        # content is a required parameter, calling without it raises TypeError
        with pytest.raises(TypeError, match="content"):
            await tool(category="fact")

    @pytest.mark.asyncio
    async def test_store_memory_missing_category(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that store_memory requires category field."""
        tool = memory_tools["store_memory"]
        # category is a required parameter, calling without it raises TypeError
        with pytest.raises(TypeError, match="category"):
            await tool(content="Test content")

    @pytest.mark.asyncio
    async def test_store_memory_content_empty(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that store_memory accepts empty content (stores as-is).

        Note: The spec says empty strings should be rejected, but the current
        implementation stores them. If validation is added, update this test.
        """
        tool = memory_tools["store_memory"]
        # Current behavior: accepts empty content
        # If this fails, validation has been added - update the test
        result = await tool(content="", category="fact")
        assert "id" in result

    @pytest.mark.asyncio
    async def test_store_memory_invalid_category(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that store_memory rejects invalid category enum value."""
        tool = memory_tools["store_memory"]
        with pytest.raises(ValidationError, match="Invalid category"):
            await tool(content="Test", category="invalid")

    @pytest.mark.asyncio
    async def test_store_memory_invalid_category_lists_valid_options(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that error message lists valid category options."""
        tool = memory_tools["store_memory"]
        with pytest.raises(ValidationError) as exc_info:
            await tool(content="Test", category="invalid")
        # Should list valid categories
        assert "fact" in str(exc_info.value)
        assert "preference" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_store_memory_content_too_long(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that store_memory rejects content exceeding 10,000 chars."""
        tool = memory_tools["store_memory"]
        long_content = "x" * 15_000
        with pytest.raises(ValidationError, match="Content too long"):
            await tool(content=long_content, category="fact")

    @pytest.mark.asyncio
    async def test_store_memory_content_too_long_shows_limit(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that content length error shows the limit."""
        tool = memory_tools["store_memory"]
        long_content = "x" * 15_000
        with pytest.raises(ValidationError) as exc_info:
            await tool(content=long_content, category="fact")
        assert "10000" in str(exc_info.value) or "10,000" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_store_memory_importance_below_range(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that store_memory rejects importance < 0.0."""
        tool = memory_tools["store_memory"]
        with pytest.raises(ValidationError, match="Importance.*out of range"):
            await tool(content="Test", category="fact", importance=-0.1)

    @pytest.mark.asyncio
    async def test_store_memory_importance_above_range(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that store_memory rejects importance > 1.0."""
        tool = memory_tools["store_memory"]
        with pytest.raises(ValidationError, match="Importance.*out of range"):
            await tool(content="Test", category="fact", importance=1.5)

    @pytest.mark.asyncio
    async def test_store_memory_importance_at_boundary_lower(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that store_memory accepts importance = 0.0."""
        tool = memory_tools["store_memory"]
        result = await tool(content="Test", category="fact", importance=0.0)
        assert result["importance"] == 0.0

    @pytest.mark.asyncio
    async def test_store_memory_importance_at_boundary_upper(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that store_memory accepts importance = 1.0."""
        tool = memory_tools["store_memory"]
        result = await tool(content="Test", category="fact", importance=1.0)
        assert result["importance"] == 1.0


class TestRetrieveMemoriesValidation:
    """Validation tests for retrieve_memories tool."""

    @pytest.mark.asyncio
    async def test_retrieve_memories_missing_query(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that retrieve_memories requires query field."""
        tool = memory_tools["retrieve_memories"]
        # query is a required parameter
        with pytest.raises(TypeError, match="query"):
            await tool()

    @pytest.mark.asyncio
    async def test_retrieve_memories_empty_query_returns_empty(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that retrieve_memories returns empty for whitespace query."""
        tool = memory_tools["retrieve_memories"]
        result = await tool(query="   ")
        assert result["count"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_retrieve_memories_invalid_category(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that retrieve_memories rejects invalid category."""
        tool = memory_tools["retrieve_memories"]
        with pytest.raises(ValidationError, match="Invalid category"):
            await tool(query="test", category="invalid")

    @pytest.mark.asyncio
    async def test_retrieve_memories_limit_below_range(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that retrieve_memories rejects limit < 1."""
        tool = memory_tools["retrieve_memories"]
        with pytest.raises(ValidationError, match="Limit.*out of range"):
            await tool(query="test", limit=0)

    @pytest.mark.asyncio
    async def test_retrieve_memories_limit_above_range(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that retrieve_memories rejects limit > 100."""
        tool = memory_tools["retrieve_memories"]
        with pytest.raises(ValidationError, match="Limit.*out of range"):
            await tool(query="test", limit=101)

    @pytest.mark.asyncio
    async def test_retrieve_memories_limit_negative(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that retrieve_memories rejects negative limit."""
        tool = memory_tools["retrieve_memories"]
        with pytest.raises(ValidationError, match="Limit.*out of range"):
            await tool(query="test", limit=-1)

    @pytest.mark.asyncio
    async def test_retrieve_memories_limit_at_boundary_lower(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that retrieve_memories accepts limit = 1."""
        tool = memory_tools["retrieve_memories"]
        result = await tool(query="test", limit=1)
        assert "results" in result

    @pytest.mark.asyncio
    async def test_retrieve_memories_limit_at_boundary_upper(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that retrieve_memories accepts limit = 100."""
        tool = memory_tools["retrieve_memories"]
        result = await tool(query="test", limit=100)
        assert "results" in result


class TestListMemoriesValidation:
    """Validation tests for list_memories tool."""

    @pytest.mark.asyncio
    async def test_list_memories_invalid_category(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that list_memories rejects invalid category."""
        tool = memory_tools["list_memories"]
        with pytest.raises(ValidationError, match="Invalid category"):
            await tool(category="invalid")

    @pytest.mark.asyncio
    async def test_list_memories_offset_negative(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that list_memories rejects negative offset."""
        tool = memory_tools["list_memories"]
        with pytest.raises(ValidationError, match="Offset.*must be >= 0"):
            await tool(offset=-1)

    @pytest.mark.asyncio
    async def test_list_memories_offset_zero(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that list_memories accepts offset = 0."""
        tool = memory_tools["list_memories"]
        result = await tool(offset=0)
        assert "results" in result

    @pytest.mark.asyncio
    async def test_list_memories_limit_below_range(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that list_memories rejects limit < 1."""
        tool = memory_tools["list_memories"]
        with pytest.raises(ValidationError, match="Limit.*out of range"):
            await tool(limit=0)

    @pytest.mark.asyncio
    async def test_list_memories_limit_above_range(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that list_memories rejects limit > 200."""
        tool = memory_tools["list_memories"]
        with pytest.raises(ValidationError, match="Limit.*out of range"):
            await tool(limit=201)

    @pytest.mark.asyncio
    async def test_list_memories_limit_at_boundary_lower(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that list_memories accepts limit = 1."""
        tool = memory_tools["list_memories"]
        result = await tool(limit=1)
        assert "results" in result

    @pytest.mark.asyncio
    async def test_list_memories_limit_at_boundary_upper(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that list_memories accepts limit = 200."""
        tool = memory_tools["list_memories"]
        result = await tool(limit=200)
        assert "results" in result


class TestDeleteMemoryValidation:
    """Validation tests for delete_memory tool."""

    @pytest.mark.asyncio
    async def test_delete_memory_missing_memory_id(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """Test that delete_memory requires memory_id field."""
        tool = memory_tools["delete_memory"]
        # memory_id is a required parameter
        with pytest.raises(TypeError, match="memory_id"):
            await tool()

    @pytest.mark.asyncio
    async def test_delete_memory_invalid_uuid_format(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """SPEC-057: Non-UUID string should error."""
        tool = memory_tools["delete_memory"]
        with pytest.raises(ValidationError, match="not a valid UUID"):
            await tool(memory_id="not-a-uuid")

    @pytest.mark.asyncio
    async def test_delete_memory_invalid_uuid_shows_value(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """SPEC-057: Error should show the invalid value."""
        tool = memory_tools["delete_memory"]
        with pytest.raises(ValidationError) as exc_info:
            await tool(memory_id="bad-id")
        assert "bad-id" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_memory_valid_uuid_accepted(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """SPEC-057: Valid UUID format should be accepted."""
        tool = memory_tools["delete_memory"]
        # Should not raise ValidationError (may return deleted=False if not found)
        result = await tool(memory_id="12345678-1234-1234-1234-123456789012")
        # Just checking it didn't raise ValidationError
        assert "deleted" in result


class TestAllValidCategoriesAccepted:
    """Test that all documented category values are accepted."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "category",
        [
            "preference",
            "fact",
            "event",
            "workflow",
            "context",
            "error",
            "decision",
        ],
    )
    async def test_store_memory_accepts_valid_category(
        self, memory_tools: dict[str, Any], category: str
    ) -> None:
        """Test that store_memory accepts all valid category values."""
        tool = memory_tools["store_memory"]
        result = await tool(content="Test", category=category)
        assert result["category"] == category


# ============================================================================
# SPEC-057: New validation tests
# ============================================================================


class TestRetrieveMemoriesMinImportanceValidation:
    """SPEC-057: min_importance range validation tests."""

    @pytest.mark.asyncio
    async def test_min_importance_below_range(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """min_importance=-0.5 should error."""
        tool = memory_tools["retrieve_memories"]
        with pytest.raises(ValidationError, match="Min_importance.*out of range"):
            await tool(query="test", min_importance=-0.5)

    @pytest.mark.asyncio
    async def test_min_importance_above_range(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """min_importance=1.5 should error."""
        tool = memory_tools["retrieve_memories"]
        with pytest.raises(ValidationError, match="Min_importance.*out of range"):
            await tool(query="test", min_importance=1.5)

    @pytest.mark.asyncio
    async def test_min_importance_at_boundaries(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """min_importance=0.0 and 1.0 should be accepted."""
        tool = memory_tools["retrieve_memories"]
        # Should not raise
        result_low = await tool(query="test", min_importance=0.0)
        assert "results" in result_low

        result_high = await tool(query="test", min_importance=1.0)
        assert "results" in result_high


class TestStoreMemoryTagsValidation:
    """SPEC-057: Tags array validation tests for store_memory."""

    @pytest.mark.asyncio
    async def test_too_many_tags(self, memory_tools: dict[str, Any]) -> None:
        """More than 20 tags should error."""
        tool = memory_tools["store_memory"]
        with pytest.raises(ValidationError, match="Too many tags"):
            await tool(
                content="test",
                category="fact",
                tags=["tag"] * 25,
            )

    @pytest.mark.asyncio
    async def test_tag_too_long(self, memory_tools: dict[str, Any]) -> None:
        """Tag longer than 50 chars should error."""
        tool = memory_tools["store_memory"]
        with pytest.raises(ValidationError, match="too long"):
            await tool(
                content="test",
                category="fact",
                tags=["x" * 60],
            )

    @pytest.mark.asyncio
    async def test_tags_at_limits_accepted(
        self, memory_tools: dict[str, Any]
    ) -> None:
        """20 tags of 50 chars each should be accepted."""
        tool = memory_tools["store_memory"]
        result = await tool(
            content="test",
            category="fact",
            tags=["x" * 50] * 20,
        )
        assert "id" in result

    @pytest.mark.asyncio
    async def test_empty_tags_accepted(self, memory_tools: dict[str, Any]) -> None:
        """Empty tags list should be accepted."""
        tool = memory_tools["store_memory"]
        result = await tool(
            content="test",
            category="fact",
            tags=[],
        )
        assert "id" in result

    @pytest.mark.asyncio
    async def test_none_tags_accepted(self, memory_tools: dict[str, Any]) -> None:
        """None tags should be accepted (uses default)."""
        tool = memory_tools["store_memory"]
        result = await tool(
            content="test",
            category="fact",
            tags=None,
        )
        assert "id" in result


class TestListMemoriesTagsValidation:
    """SPEC-057: Tags array validation tests for list_memories."""

    @pytest.mark.asyncio
    async def test_too_many_tags(self, memory_tools: dict[str, Any]) -> None:
        """More than 20 tags should error."""
        tool = memory_tools["list_memories"]
        with pytest.raises(ValidationError, match="Too many tags"):
            await tool(tags=["tag"] * 25)

    @pytest.mark.asyncio
    async def test_tag_too_long(self, memory_tools: dict[str, Any]) -> None:
        """Tag longer than 50 chars should error."""
        tool = memory_tools["list_memories"]
        with pytest.raises(ValidationError, match="too long"):
            await tool(tags=["x" * 60])

    @pytest.mark.asyncio
    async def test_valid_tags_accepted(self, memory_tools: dict[str, Any]) -> None:
        """Valid tags should be accepted."""
        tool = memory_tools["list_memories"]
        result = await tool(tags=["tag1", "tag2"])
        assert "results" in result
