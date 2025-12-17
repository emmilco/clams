"""Input validation tests for code tools.

Tests cover:
- index_codebase: directory, project, recursive
- search_code: query, project, language, limit
- find_similar_code: snippet, project, limit

This test module verifies that all validation constraints are enforced
with informative error messages.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from clams.server.errors import ValidationError


class TestIndexCodebaseValidation:
    """Validation tests for index_codebase tool."""

    @pytest.mark.asyncio
    async def test_index_codebase_missing_directory(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Test that index_codebase requires directory field."""
        tool = code_tools["index_codebase"]
        with pytest.raises(TypeError, match="directory"):
            await tool(project="test-project")

    @pytest.mark.asyncio
    async def test_index_codebase_missing_project(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Test that index_codebase requires project field."""
        tool = code_tools["index_codebase"]
        with pytest.raises(TypeError, match="project"):
            await tool(directory="/tmp")

    @pytest.mark.asyncio
    async def test_index_codebase_invalid_directory_not_found(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Test that index_codebase rejects non-existent directory."""
        tool = code_tools["index_codebase"]
        with pytest.raises(ValidationError, match="Directory not found"):
            await tool(
                directory="/nonexistent/path/to/directory",
                project="test-project",
            )

    @pytest.mark.asyncio
    async def test_index_codebase_invalid_directory_is_file(
        self, code_tools: dict[str, Any], tmp_path: Any
    ) -> None:
        """Test that index_codebase rejects file path as directory."""
        # Create a file
        file_path = tmp_path / "testfile.txt"
        file_path.write_text("test")

        tool = code_tools["index_codebase"]
        with pytest.raises(ValidationError, match="Not a directory"):
            await tool(
                directory=str(file_path),
                project="test-project",
            )

    @pytest.mark.asyncio
    async def test_index_codebase_valid_directory(
        self, code_tools: dict[str, Any], mock_services: Any, tmp_path: Any
    ) -> None:
        """Test that index_codebase accepts valid directory."""
        # Mock the code_indexer
        mock_stats = MagicMock()
        mock_stats.files_indexed = 10
        mock_stats.units_indexed = 50
        mock_stats.files_skipped = 2
        mock_stats.errors = []
        mock_stats.duration_ms = 100
        mock_services.code_indexer.index_directory.return_value = mock_stats

        tool = code_tools["index_codebase"]
        result = await tool(
            directory=str(tmp_path),
            project="test-project",
        )
        assert result["project"] == "test-project"


class TestSearchCodeValidation:
    """Validation tests for search_code tool."""

    @pytest.mark.asyncio
    async def test_search_code_missing_query(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Test that search_code requires query field."""
        tool = code_tools["search_code"]
        with pytest.raises(TypeError, match="query"):
            await tool()

    @pytest.mark.asyncio
    async def test_search_code_empty_query_returns_empty(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Test that search_code returns empty for whitespace query."""
        tool = code_tools["search_code"]
        result = await tool(query="   ")
        assert result["count"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_search_code_limit_below_range(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Test that search_code rejects limit < 1."""
        tool = code_tools["search_code"]
        with pytest.raises(ValidationError, match="Limit.*out of range"):
            await tool(query="test", limit=0)

    @pytest.mark.asyncio
    async def test_search_code_limit_above_range(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Test that search_code rejects limit > 50."""
        tool = code_tools["search_code"]
        with pytest.raises(ValidationError, match="Limit.*out of range"):
            await tool(query="test", limit=51)

    @pytest.mark.asyncio
    async def test_search_code_limit_negative(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Test that search_code rejects negative limit."""
        tool = code_tools["search_code"]
        with pytest.raises(ValidationError, match="Limit.*out of range"):
            await tool(query="test", limit=-1)

    @pytest.mark.asyncio
    async def test_search_code_limit_at_boundary_lower(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Test that search_code accepts limit = 1."""
        tool = code_tools["search_code"]
        result = await tool(query="test", limit=1)
        assert "results" in result

    @pytest.mark.asyncio
    async def test_search_code_limit_at_boundary_upper(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Test that search_code accepts limit = 50."""
        tool = code_tools["search_code"]
        result = await tool(query="test", limit=50)
        assert "results" in result


class TestFindSimilarCodeValidation:
    """Validation tests for find_similar_code tool."""

    @pytest.mark.asyncio
    async def test_find_similar_code_missing_snippet(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Test that find_similar_code requires snippet field."""
        tool = code_tools["find_similar_code"]
        with pytest.raises(TypeError, match="snippet"):
            await tool()

    @pytest.mark.asyncio
    async def test_find_similar_code_empty_snippet_returns_empty(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Test that find_similar_code returns empty for whitespace snippet."""
        tool = code_tools["find_similar_code"]
        result = await tool(snippet="   ")
        assert result["count"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_find_similar_code_snippet_too_long(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Test that find_similar_code rejects snippet exceeding 5,000 chars."""
        tool = code_tools["find_similar_code"]
        long_snippet = "x" * 6000
        with pytest.raises(ValidationError, match="Snippet too long"):
            await tool(snippet=long_snippet)

    @pytest.mark.asyncio
    async def test_find_similar_code_snippet_too_long_shows_limit(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Test that snippet length error shows the limit."""
        tool = code_tools["find_similar_code"]
        long_snippet = "x" * 6000
        with pytest.raises(ValidationError) as exc_info:
            await tool(snippet=long_snippet)
        assert "5000" in str(exc_info.value) or "5,000" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_find_similar_code_limit_below_range(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Test that find_similar_code rejects limit < 1."""
        tool = code_tools["find_similar_code"]
        with pytest.raises(ValidationError, match="Limit.*out of range"):
            await tool(snippet="test code", limit=0)

    @pytest.mark.asyncio
    async def test_find_similar_code_limit_above_range(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Test that find_similar_code rejects limit > 50."""
        tool = code_tools["find_similar_code"]
        with pytest.raises(ValidationError, match="Limit.*out of range"):
            await tool(snippet="test code", limit=51)

    @pytest.mark.asyncio
    async def test_find_similar_code_limit_at_boundary_lower(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Test that find_similar_code accepts limit = 1."""
        tool = code_tools["find_similar_code"]
        result = await tool(snippet="test code", limit=1)
        assert "results" in result

    @pytest.mark.asyncio
    async def test_find_similar_code_limit_at_boundary_upper(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Test that find_similar_code accepts limit = 50."""
        tool = code_tools["find_similar_code"]
        result = await tool(snippet="test code", limit=50)
        assert "results" in result
