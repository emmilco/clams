"""Tests for search tools."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from clams.search.searcher import Searcher
from clams.server.tools.search import get_search_tools


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
def tools(searcher: Searcher) -> dict[str, Any]:
    """Get search tools."""
    return get_search_tools(searcher)


class TestSearchExperiences:
    """Tests for search_experiences tool."""

    @pytest.mark.asyncio
    async def test_search_experiences_success(
        self, tools: dict[str, Any]
    ) -> None:
        """Test successful experience search."""
        tool = tools["search_experiences"]
        result = await tool(
            query="How to debug async issues",
            axis="full",
        )

        assert "error" not in result
        assert "results" in result
        assert "count" in result

    @pytest.mark.asyncio
    async def test_search_experiences_empty_query(
        self, tools: dict[str, Any]
    ) -> None:
        """Test search with empty query returns empty results."""
        tool = tools["search_experiences"]
        result = await tool(query="")

        assert "error" not in result
        assert result["results"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_search_experiences_with_filters(
        self, tools: dict[str, Any]
    ) -> None:
        """Test search with domain and outcome filters."""
        tool = tools["search_experiences"]
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
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for invalid axis."""
        tool = tools["search_experiences"]
        result = await tool(
            query="test query",
            axis="invalid",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid axis" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_search_experiences_invalid_domain(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for invalid domain filter."""
        tool = tools["search_experiences"]
        result = await tool(
            query="test query",
            domain="invalid",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid domain" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_search_experiences_invalid_outcome(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for invalid outcome filter."""
        tool = tools["search_experiences"]
        result = await tool(
            query="test query",
            outcome="invalid",
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "Invalid outcome status" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_search_experiences_invalid_limit(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for invalid limit."""
        tool = tools["search_experiences"]
        result = await tool(
            query="test query",
            limit=0,
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "between 1 and 50" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_search_experiences_limit_max(
        self, tools: dict[str, Any]
    ) -> None:
        """Test validation error for limit exceeding max."""
        tool = tools["search_experiences"]
        result = await tool(
            query="test query",
            limit=51,
        )

        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "between 1 and 50" in result["error"]["message"]
