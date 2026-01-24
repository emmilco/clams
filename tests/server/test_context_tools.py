"""Tests for context assembly tools."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from clams.server.tools.context import get_context_tools


@dataclass
class MockValue:
    """Mock Value dataclass for testing."""

    text: str


@dataclass
class MockExperienceResult:
    """Mock ExperienceResult dataclass for testing.

    IMPORTANT: This mock must have field names matching the production
    ExperienceResult at clams.search.results.ExperienceResult.

    This is a simplified mock that only includes fields used by tests.
    Field parity is verified by tests/infrastructure/test_mock_parity.py.
    See BUG-040 for an example of bugs caused by field name mismatches.
    """

    domain: str
    goal: str
    outcome_status: str


@pytest.fixture
def mock_searcher() -> MagicMock:
    """Create mock Searcher."""
    searcher = MagicMock()
    searcher.search_experiences = AsyncMock(return_value=[])
    return searcher


@pytest.fixture
def mock_value_store() -> MagicMock:
    """Create mock ValueStore."""
    store = MagicMock()
    store.list_values = AsyncMock(return_value=[])
    return store


class TestAssembleContext:
    """Test assemble_context tool."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_data(
        self, mock_searcher: MagicMock, mock_value_store: MagicMock
    ) -> None:
        """assemble_context should return empty markdown when no data."""
        tools = get_context_tools(mock_searcher, mock_value_store)
        result = await tools["assemble_context"](query="test query")

        assert result["markdown"] == ""
        assert result["token_count"] == 0
        assert result["item_count"] == 0
        assert result["truncated"] is False

    @pytest.mark.asyncio
    async def test_includes_values_in_context(
        self, mock_searcher: MagicMock, mock_value_store: MagicMock
    ) -> None:
        """assemble_context should include values in markdown."""
        mock_value_store.list_values = AsyncMock(
            return_value=[
                MockValue(text="Value 1: Always test your code"),
                MockValue(text="Value 2: Keep functions small"),
            ]
        )

        tools = get_context_tools(mock_searcher, mock_value_store)
        result = await tools["assemble_context"](
            query="test",
            context_types=["values"],
        )

        assert "## Learned Values" in result["markdown"]
        assert "Always test your code" in result["markdown"]
        assert "Keep functions small" in result["markdown"]
        assert result["item_count"] == 2

    @pytest.mark.asyncio
    async def test_includes_experiences_in_context(
        self, mock_searcher: MagicMock, mock_value_store: MagicMock
    ) -> None:
        """assemble_context should include experiences in markdown."""
        mock_searcher.search_experiences = AsyncMock(
            return_value=[
                MockExperienceResult(
                    domain="debugging",
                    goal="Fix memory leak",
                    outcome_status="confirmed",
                ),
                MockExperienceResult(
                    domain="testing",
                    goal="Add unit tests",
                    outcome_status="falsified",
                ),
            ]
        )

        tools = get_context_tools(mock_searcher, mock_value_store)
        result = await tools["assemble_context"](
            query="how to debug",
            context_types=["experiences"],
        )

        assert "## Relevant Experiences" in result["markdown"]
        assert "debugging" in result["markdown"]
        assert "Fix memory leak" in result["markdown"]
        assert result["item_count"] == 2

    @pytest.mark.asyncio
    async def test_includes_both_by_default(
        self, mock_searcher: MagicMock, mock_value_store: MagicMock
    ) -> None:
        """assemble_context should include both values and experiences by default."""
        mock_value_store.list_values = AsyncMock(
            return_value=[MockValue(text="A value")]
        )
        mock_searcher.search_experiences = AsyncMock(
            return_value=[
                MockExperienceResult(
                    domain="test", goal="Test goal", outcome_status="confirmed"
                )
            ]
        )

        tools = get_context_tools(mock_searcher, mock_value_store)
        result = await tools["assemble_context"](query="test")

        assert "## Learned Values" in result["markdown"]
        assert "## Relevant Experiences" in result["markdown"]
        assert result["item_count"] == 2

    @pytest.mark.asyncio
    async def test_respects_limit_parameter_for_values(
        self, mock_searcher: MagicMock, mock_value_store: MagicMock
    ) -> None:
        """assemble_context should slice values to limit."""
        # Return more values than requested
        mock_value_store.list_values = AsyncMock(
            return_value=[
                MockValue(text=f"Value {i}") for i in range(10)
            ]
        )

        tools = get_context_tools(mock_searcher, mock_value_store)
        result = await tools["assemble_context"](
            query="test", limit=3, context_types=["values"]
        )

        # Should only have 3 values
        assert result["item_count"] == 3

    @pytest.mark.asyncio
    async def test_limits_experiences_to_5(
        self, mock_searcher: MagicMock, mock_value_store: MagicMock
    ) -> None:
        """assemble_context should limit experiences to 5 max."""
        tools = get_context_tools(mock_searcher, mock_value_store)
        await tools["assemble_context"](query="test", limit=20)

        mock_searcher.search_experiences.assert_called_with(
            query="test",
            limit=5,  # Capped at 5
        )

    @pytest.mark.asyncio
    async def test_calculates_token_count(
        self, mock_searcher: MagicMock, mock_value_store: MagicMock
    ) -> None:
        """assemble_context should estimate token count."""
        mock_value_store.list_values = AsyncMock(
            return_value=[MockValue(text="A" * 400)]  # 400 chars ~= 100 tokens
        )

        tools = get_context_tools(mock_searcher, mock_value_store)
        result = await tools["assemble_context"](
            query="test", context_types=["values"]
        )

        # Token count should be roughly len(markdown) / 4
        assert result["token_count"] > 0
        assert result["token_count"] == len(result["markdown"]) // 4

    @pytest.mark.asyncio
    async def test_reports_truncation(
        self, mock_searcher: MagicMock, mock_value_store: MagicMock
    ) -> None:
        """assemble_context should report when content exceeds max_tokens."""
        # Create a lot of content
        mock_value_store.list_values = AsyncMock(
            return_value=[MockValue(text="A" * 8000)]  # 8000 chars = ~2000 tokens
        )

        tools = get_context_tools(mock_searcher, mock_value_store)
        result = await tools["assemble_context"](
            query="test",
            context_types=["values"],
            max_tokens=1500,
        )

        assert result["truncated"] is True

    @pytest.mark.asyncio
    async def test_handles_value_store_error(
        self, mock_searcher: MagicMock, mock_value_store: MagicMock
    ) -> None:
        """assemble_context should handle value store errors gracefully."""
        mock_value_store.list_values = AsyncMock(
            side_effect=Exception("Database error")
        )

        tools = get_context_tools(mock_searcher, mock_value_store)
        result = await tools["assemble_context"](
            query="test", context_types=["values"]
        )

        # Should not raise, just return empty
        assert result["markdown"] == ""
        assert result["item_count"] == 0

    @pytest.mark.asyncio
    async def test_handles_searcher_error(
        self, mock_searcher: MagicMock, mock_value_store: MagicMock
    ) -> None:
        """assemble_context should handle searcher errors gracefully."""
        mock_searcher.search_experiences = AsyncMock(
            side_effect=Exception("Search error")
        )

        tools = get_context_tools(mock_searcher, mock_value_store)
        result = await tools["assemble_context"](
            query="test", context_types=["experiences"]
        )

        # Should not raise, just return empty
        assert result["markdown"] == ""
        assert result["item_count"] == 0

    @pytest.mark.asyncio
    async def test_skips_experiences_without_query(
        self, mock_searcher: MagicMock, mock_value_store: MagicMock
    ) -> None:
        """assemble_context should skip experience search with empty query."""
        tools = get_context_tools(mock_searcher, mock_value_store)
        await tools["assemble_context"](query="", context_types=["experiences"])

        mock_searcher.search_experiences.assert_not_called()
