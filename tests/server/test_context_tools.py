"""Tests for context assembly tools."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from calm.tools.context import get_context_tools


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Create mock vector store."""
    store = AsyncMock()
    store.search = AsyncMock(return_value=[])
    store.scroll = AsyncMock(return_value=[])
    return store


@pytest.fixture
def mock_semantic_embedder() -> AsyncMock:
    """Create mock semantic embedding service."""
    service = AsyncMock()
    service.embed.return_value = [0.1] * 768
    service.dimension = 768
    return service


class TestAssembleContext:
    """Test assemble_context tool."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_data(
        self, mock_vector_store: AsyncMock, mock_semantic_embedder: AsyncMock
    ) -> None:
        """assemble_context should return empty markdown when no data."""
        # Make scroll/search raise "not found" to simulate empty collections
        mock_vector_store.scroll.side_effect = Exception("Collection not found")
        mock_vector_store.search.side_effect = Exception("Collection not found")
        tools = get_context_tools(mock_vector_store, mock_semantic_embedder)
        result = await tools["assemble_context"](query="test query")

        assert result["markdown"] == ""
        assert result["token_count"] == 0
        assert result["item_count"] == 0
        assert result["truncated"] is False

    @pytest.mark.asyncio
    async def test_includes_values_in_context(
        self, mock_vector_store: AsyncMock, mock_semantic_embedder: AsyncMock
    ) -> None:
        """assemble_context should include values in markdown."""
        # Mock scroll to return values
        mock_vector_store.scroll.return_value = [
            MagicMock(
                id="v1",
                payload={"text": "Value 1: Always test your code"},
            ),
            MagicMock(
                id="v2",
                payload={"text": "Value 2: Keep functions small"},
            ),
        ]
        # Make search raise not found so experiences section is empty
        mock_vector_store.search.side_effect = Exception("Collection not found")

        tools = get_context_tools(mock_vector_store, mock_semantic_embedder)
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
        self, mock_vector_store: AsyncMock, mock_semantic_embedder: AsyncMock
    ) -> None:
        """assemble_context should include experiences in markdown."""
        # Make scroll raise not found so values section is empty
        mock_vector_store.scroll.side_effect = Exception("Collection not found")
        # Mock search to return experiences
        mock_vector_store.search.return_value = [
            MagicMock(
                id="e1",
                score=0.9,
                payload={
                    "domain": "debugging",
                    "goal": "Fix memory leak",
                    "outcome_status": "confirmed",
                },
            ),
            MagicMock(
                id="e2",
                score=0.8,
                payload={
                    "domain": "testing",
                    "goal": "Add unit tests",
                    "outcome_status": "falsified",
                },
            ),
        ]

        tools = get_context_tools(mock_vector_store, mock_semantic_embedder)
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
        self, mock_vector_store: AsyncMock, mock_semantic_embedder: AsyncMock
    ) -> None:
        """assemble_context should include both values and experiences by default."""
        # Mock scroll for values
        mock_vector_store.scroll.return_value = [
            MagicMock(id="v1", payload={"text": "A value"}),
        ]
        # Mock search for experiences
        mock_vector_store.search.return_value = [
            MagicMock(
                id="e1",
                score=0.9,
                payload={
                    "domain": "test",
                    "goal": "Test goal",
                    "outcome_status": "confirmed",
                },
            ),
        ]

        tools = get_context_tools(mock_vector_store, mock_semantic_embedder)
        result = await tools["assemble_context"](query="test")

        assert "## Learned Values" in result["markdown"]
        assert "## Relevant Experiences" in result["markdown"]
        assert result["item_count"] == 2

    @pytest.mark.asyncio
    async def test_calculates_token_count(
        self, mock_vector_store: AsyncMock, mock_semantic_embedder: AsyncMock
    ) -> None:
        """assemble_context should estimate token count."""
        mock_vector_store.scroll.return_value = [
            MagicMock(id="v1", payload={"text": "A" * 400}),
        ]
        mock_vector_store.search.side_effect = Exception("Collection not found")

        tools = get_context_tools(mock_vector_store, mock_semantic_embedder)
        result = await tools["assemble_context"](
            query="test", context_types=["values"]
        )

        # Token count should be roughly len(markdown) / 4
        assert result["token_count"] > 0
        assert result["token_count"] == len(result["markdown"]) // 4

    @pytest.mark.asyncio
    async def test_reports_truncation(
        self, mock_vector_store: AsyncMock, mock_semantic_embedder: AsyncMock
    ) -> None:
        """assemble_context should report when content exceeds max_tokens."""
        # Create a lot of content
        mock_vector_store.scroll.return_value = [
            MagicMock(id="v1", payload={"text": "A" * 8000}),
        ]
        mock_vector_store.search.side_effect = Exception("Collection not found")

        tools = get_context_tools(mock_vector_store, mock_semantic_embedder)
        result = await tools["assemble_context"](
            query="test",
            context_types=["values"],
            max_tokens=1500,
        )

        assert result["truncated"] is True

    @pytest.mark.asyncio
    async def test_handles_value_store_error(
        self, mock_vector_store: AsyncMock, mock_semantic_embedder: AsyncMock
    ) -> None:
        """assemble_context should handle value store errors gracefully."""
        mock_vector_store.scroll.side_effect = Exception("Database error")
        mock_vector_store.search.side_effect = Exception("Database error")

        tools = get_context_tools(mock_vector_store, mock_semantic_embedder)
        result = await tools["assemble_context"](
            query="test", context_types=["values"]
        )

        # Should not raise, just return empty
        assert result["markdown"] == ""
        assert result["item_count"] == 0

    @pytest.mark.asyncio
    async def test_handles_searcher_error(
        self, mock_vector_store: AsyncMock, mock_semantic_embedder: AsyncMock
    ) -> None:
        """assemble_context should handle searcher errors gracefully."""
        mock_vector_store.scroll.side_effect = Exception("Search error")
        mock_vector_store.search.side_effect = Exception("Search error")

        tools = get_context_tools(mock_vector_store, mock_semantic_embedder)
        result = await tools["assemble_context"](
            query="test", context_types=["experiences"]
        )

        # Should not raise, just return empty
        assert result["markdown"] == ""
        assert result["item_count"] == 0

    @pytest.mark.asyncio
    async def test_skips_experiences_without_query(
        self, mock_vector_store: AsyncMock, mock_semantic_embedder: AsyncMock
    ) -> None:
        """assemble_context should skip experience search with empty query."""
        tools = get_context_tools(mock_vector_store, mock_semantic_embedder)
        result = await tools["assemble_context"](query="", context_types=["experiences"])

        # Empty query returns empty result
        assert result["markdown"] == ""
        assert result["item_count"] == 0
