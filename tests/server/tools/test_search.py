"""Tests for search tools."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from learning_memory_server.search import Searcher
from learning_memory_server.server.tools.search import register_search_tools


@pytest.fixture
def searcher() -> Searcher:
    """Create a mock Searcher."""
    searcher = Searcher(
        embedding_service=MagicMock(),
        vector_store=MagicMock(),
    )
    # Mock the search_experiences method
    searcher.search_experiences = AsyncMock(return_value=[])
    return searcher


@pytest.fixture
def mock_server() -> MagicMock:
    """Create a mock MCP server with tool registry."""
    server = MagicMock()
    server.tools = {}

    def register_tool(func):  # type: ignore[no-untyped-def]
        server.tools[func.__name__] = func
        return func

    server.call_tool = lambda: register_tool
    return server


@pytest.fixture
def registered_tools(
    mock_server: MagicMock,
    searcher: Searcher,
) -> MagicMock:
    """Register search tools and return the server."""
    register_search_tools(mock_server, searcher)
    return mock_server


class TestSearchExperiences:
    """Tests for search_experiences tool."""

    @pytest.mark.asyncio
    async def test_search_experiences_success(
        self, registered_tools: MagicMock
    ) -> None:
        """Test successful experience search."""
        tool = registered_tools.tools["search_experiences"]
        result = await tool(
            query="How to debug async issues",
            axis="full",
        )

        assert "error" not in result
        assert "results" in result
        assert "count" in result

    @pytest.mark.asyncio
    async def test_search_experiences_empty_query(
        self, registered_tools: MagicMock
    ) -> None:
        """Test search with empty query returns empty results."""
        tool = registered_tools.tools["search_experiences"]
        result = await tool(query="")

        assert "error" not in result
        assert result["results"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_search_experiences_with_filters(
        self, registered_tools: MagicMock
    ) -> None:
        """Test search with domain and outcome filters."""
        tool = registered_tools.tools["search_experiences"]
        result = await tool(
            query="debugging patterns",
            axis="full",
            domain="debugging",
            outcome="confirmed",
            limit=20,
        )

        assert "error" not in result
        assert "results" in result

    @pytest.mark.asyncio
    async def test_search_experiences_invalid_axis(
        self, registered_tools: MagicMock
    ) -> None:
        """Test validation error for invalid axis."""
        tool = registered_tools.tools["search_experiences"]
        result = await tool(
            query="test query",
            axis="invalid",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid axis" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_search_experiences_invalid_domain(
        self, registered_tools: MagicMock
    ) -> None:
        """Test validation error for invalid domain filter."""
        tool = registered_tools.tools["search_experiences"]
        result = await tool(
            query="test query",
            domain="invalid",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid domain" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_search_experiences_invalid_outcome(
        self, registered_tools: MagicMock
    ) -> None:
        """Test validation error for invalid outcome filter."""
        tool = registered_tools.tools["search_experiences"]
        result = await tool(
            query="test query",
            outcome="invalid",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid outcome status" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_search_experiences_invalid_limit(
        self, registered_tools: MagicMock
    ) -> None:
        """Test validation error for invalid limit."""
        tool = registered_tools.tools["search_experiences"]
        result = await tool(
            query="test query",
            limit=0,
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "between 1 and 50" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_search_experiences_limit_max(
        self, registered_tools: MagicMock
    ) -> None:
        """Test validation error for limit exceeding max."""
        tool = registered_tools.tools["search_experiences"]
        result = await tool(
            query="test query",
            limit=51,
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "between 1 and 50" in result["error"]["message"]
