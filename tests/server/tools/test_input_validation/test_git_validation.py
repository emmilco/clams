"""Input validation tests for git tools.

Tests cover:
- index_commits: since, limit, force
- search_commits: query, author, since, limit
- get_file_history: path, limit
- get_churn_hotspots: days, limit
- get_code_authors: path

This test module verifies that all validation constraints are enforced
with informative error messages.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from clams.server.errors import ValidationError


class TestIndexCommitsValidation:
    """Validation tests for index_commits tool."""

    @pytest.mark.asyncio
    async def test_index_commits_since_invalid_format(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that index_commits rejects invalid date format."""
        tool = git_tools["index_commits"]
        with pytest.raises(ValidationError, match="Invalid date format"):
            await tool(since="not-a-date")

    @pytest.mark.asyncio
    async def test_index_commits_since_invalid_format_shows_expected(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that date format error shows expected format."""
        tool = git_tools["index_commits"]
        with pytest.raises(ValidationError) as exc_info:
            await tool(since="not-a-date")
        assert "YYYY-MM-DD" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_index_commits_limit_below_one(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that index_commits rejects limit < 1."""
        tool = git_tools["index_commits"]
        with pytest.raises(ValidationError, match="Limit must be positive"):
            await tool(limit=0)

    @pytest.mark.asyncio
    async def test_index_commits_limit_negative(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that index_commits rejects negative limit."""
        tool = git_tools["index_commits"]
        with pytest.raises(ValidationError, match="Limit must be positive"):
            await tool(limit=-1)

    @pytest.mark.asyncio
    async def test_index_commits_valid_since_date(
        self, git_tools: dict[str, Any], mock_services: Any
    ) -> None:
        """Test that index_commits accepts valid ISO date."""
        # Mock the git_analyzer
        mock_stats = MagicMock()
        mock_stats.commits_indexed = 10
        mock_stats.commits_skipped = 2
        mock_stats.duration_ms = 100
        mock_stats.errors = []
        mock_services.git_analyzer.index_commits.return_value = mock_stats

        tool = git_tools["index_commits"]
        result = await tool(since="2024-01-01")
        assert "commits_indexed" in result


class TestSearchCommitsValidation:
    """Validation tests for search_commits tool."""

    @pytest.mark.asyncio
    async def test_search_commits_missing_query(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that search_commits requires query field."""
        tool = git_tools["search_commits"]
        with pytest.raises(TypeError, match="query"):
            await tool()

    @pytest.mark.asyncio
    async def test_search_commits_empty_query_returns_empty(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that search_commits returns empty for whitespace query."""
        tool = git_tools["search_commits"]
        result = await tool(query="   ")
        assert result["count"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_search_commits_limit_below_range(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that search_commits rejects limit < 1."""
        tool = git_tools["search_commits"]
        with pytest.raises(ValidationError, match="Limit.*out of range"):
            await tool(query="test", limit=0)

    @pytest.mark.asyncio
    async def test_search_commits_limit_above_range(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that search_commits rejects limit > 50."""
        tool = git_tools["search_commits"]
        with pytest.raises(ValidationError, match="Limit.*out of range"):
            await tool(query="test", limit=51)

    @pytest.mark.asyncio
    async def test_search_commits_limit_negative(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that search_commits rejects negative limit."""
        tool = git_tools["search_commits"]
        with pytest.raises(ValidationError, match="Limit.*out of range"):
            await tool(query="test", limit=-1)

    @pytest.mark.asyncio
    async def test_search_commits_since_invalid_format(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that search_commits rejects invalid date format."""
        tool = git_tools["search_commits"]
        with pytest.raises(ValidationError, match="Invalid date format"):
            await tool(query="test", since="not-a-date")

    @pytest.mark.asyncio
    async def test_search_commits_limit_at_boundary_lower(
        self, git_tools: dict[str, Any], mock_services: Any
    ) -> None:
        """Test that search_commits accepts limit = 1."""
        mock_services.git_analyzer.search_commits.return_value = []
        tool = git_tools["search_commits"]
        result = await tool(query="test", limit=1)
        assert "results" in result

    @pytest.mark.asyncio
    async def test_search_commits_limit_at_boundary_upper(
        self, git_tools: dict[str, Any], mock_services: Any
    ) -> None:
        """Test that search_commits accepts limit = 50."""
        mock_services.git_analyzer.search_commits.return_value = []
        tool = git_tools["search_commits"]
        result = await tool(query="test", limit=50)
        assert "results" in result


class TestGetFileHistoryValidation:
    """Validation tests for get_file_history tool."""

    @pytest.mark.asyncio
    async def test_get_file_history_missing_path(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that get_file_history requires path field."""
        tool = git_tools["get_file_history"]
        with pytest.raises(TypeError, match="path"):
            await tool()

    @pytest.mark.asyncio
    async def test_get_file_history_limit_below_range(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that get_file_history rejects limit < 1."""
        tool = git_tools["get_file_history"]
        with pytest.raises(ValidationError, match="Limit.*out of range"):
            await tool(path="src/main.py", limit=0)

    @pytest.mark.asyncio
    async def test_get_file_history_limit_above_range(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that get_file_history rejects limit > 500."""
        tool = git_tools["get_file_history"]
        with pytest.raises(ValidationError, match="Limit.*out of range"):
            await tool(path="src/main.py", limit=501)

    @pytest.mark.asyncio
    async def test_get_file_history_limit_at_boundary_lower(
        self, git_tools: dict[str, Any], mock_services: Any
    ) -> None:
        """Test that get_file_history accepts limit = 1."""
        mock_services.git_analyzer.git_reader.get_file_history.return_value = []
        tool = git_tools["get_file_history"]
        result = await tool(path="src/main.py", limit=1)
        assert "results" in result

    @pytest.mark.asyncio
    async def test_get_file_history_limit_at_boundary_upper(
        self, git_tools: dict[str, Any], mock_services: Any
    ) -> None:
        """Test that get_file_history accepts limit = 500."""
        mock_services.git_analyzer.git_reader.get_file_history.return_value = []
        tool = git_tools["get_file_history"]
        result = await tool(path="src/main.py", limit=500)
        assert "results" in result

    @pytest.mark.asyncio
    async def test_get_file_history_file_not_found(
        self, git_tools: dict[str, Any], mock_services: Any
    ) -> None:
        """Test that get_file_history reports file not found."""
        mock_services.git_analyzer.git_reader.get_file_history.side_effect = (
            FileNotFoundError("File not found")
        )
        tool = git_tools["get_file_history"]
        with pytest.raises(ValidationError, match="File not found"):
            await tool(path="nonexistent/file.py")


class TestGetChurnHotspotsValidation:
    """Validation tests for get_churn_hotspots tool."""

    @pytest.mark.asyncio
    async def test_get_churn_hotspots_days_below_range(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that get_churn_hotspots rejects days < 1."""
        tool = git_tools["get_churn_hotspots"]
        with pytest.raises(ValidationError, match="Days.*out of range"):
            await tool(days=0)

    @pytest.mark.asyncio
    async def test_get_churn_hotspots_days_above_range(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that get_churn_hotspots rejects days > 365."""
        tool = git_tools["get_churn_hotspots"]
        with pytest.raises(ValidationError, match="Days.*out of range"):
            await tool(days=366)

    @pytest.mark.asyncio
    async def test_get_churn_hotspots_days_negative(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that get_churn_hotspots rejects negative days."""
        tool = git_tools["get_churn_hotspots"]
        with pytest.raises(ValidationError, match="Days.*out of range"):
            await tool(days=-1)

    @pytest.mark.asyncio
    async def test_get_churn_hotspots_limit_below_range(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that get_churn_hotspots rejects limit < 1."""
        tool = git_tools["get_churn_hotspots"]
        with pytest.raises(ValidationError, match="Limit.*out of range"):
            await tool(limit=0)

    @pytest.mark.asyncio
    async def test_get_churn_hotspots_limit_above_range(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that get_churn_hotspots rejects limit > 50."""
        tool = git_tools["get_churn_hotspots"]
        with pytest.raises(ValidationError, match="Limit.*out of range"):
            await tool(limit=51)

    @pytest.mark.asyncio
    async def test_get_churn_hotspots_days_at_boundary_lower(
        self, git_tools: dict[str, Any], mock_services: Any
    ) -> None:
        """Test that get_churn_hotspots accepts days = 1."""
        mock_services.git_analyzer.get_churn_hotspots.return_value = []
        tool = git_tools["get_churn_hotspots"]
        result = await tool(days=1)
        assert "results" in result

    @pytest.mark.asyncio
    async def test_get_churn_hotspots_days_at_boundary_upper(
        self, git_tools: dict[str, Any], mock_services: Any
    ) -> None:
        """Test that get_churn_hotspots accepts days = 365."""
        mock_services.git_analyzer.get_churn_hotspots.return_value = []
        tool = git_tools["get_churn_hotspots"]
        result = await tool(days=365)
        assert "results" in result


class TestGetCodeAuthorsValidation:
    """Validation tests for get_code_authors tool."""

    @pytest.mark.asyncio
    async def test_get_code_authors_missing_path(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that get_code_authors requires path field."""
        tool = git_tools["get_code_authors"]
        with pytest.raises(TypeError, match="path"):
            await tool()

    @pytest.mark.asyncio
    async def test_get_code_authors_file_not_found(
        self, git_tools: dict[str, Any], mock_services: Any
    ) -> None:
        """Test that get_code_authors reports file not found."""
        mock_services.git_analyzer.get_file_authors.side_effect = (
            FileNotFoundError("File not found")
        )
        tool = git_tools["get_code_authors"]
        with pytest.raises(ValidationError, match="File not found"):
            await tool(path="nonexistent/file.py")

    @pytest.mark.asyncio
    async def test_get_code_authors_valid_path(
        self, git_tools: dict[str, Any], mock_services: Any
    ) -> None:
        """Test that get_code_authors accepts valid path."""
        mock_services.git_analyzer.get_file_authors.return_value = []
        tool = git_tools["get_code_authors"]
        result = await tool(path="src/main.py")
        assert "results" in result
