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

import re
from typing import Any
from unittest.mock import MagicMock

import pytest


class TestIndexCommitsValidation:
    """Validation tests for index_commits tool."""

    @pytest.mark.asyncio
    async def test_index_commits_since_invalid_format(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that index_commits rejects invalid date format."""
        tool = git_tools["index_commits"]
        result = await tool(since="not-a-date")
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Invalid date format", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_index_commits_since_invalid_format_shows_expected(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that date format error shows expected format."""
        tool = git_tools["index_commits"]
        result = await tool(since="not-a-date")
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "YYYY-MM-DD" in result["error"]["message"]
    @pytest.mark.asyncio
    async def test_index_commits_limit_below_one(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that index_commits rejects limit < 1."""
        tool = git_tools["index_commits"]
        result = await tool(limit=0)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Limit must be positive", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_index_commits_limit_negative(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that index_commits rejects negative limit."""
        tool = git_tools["index_commits"]
        result = await tool(limit=-1)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Limit must be positive", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_index_commits_valid_since_date(
        self, git_tools: dict[str, Any], mock_git_analyzer: Any
    ) -> None:
        """Test that index_commits accepts valid ISO date."""
        # Mock the git_analyzer
        mock_stats = MagicMock()
        mock_stats.commits_indexed = 10
        mock_stats.commits_skipped = 2
        mock_stats.duration_ms = 100
        mock_stats.errors = []
        mock_git_analyzer.index_commits.return_value = mock_stats

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
        result = await tool(query="test", limit=0)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Limit.*out of range", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_search_commits_limit_above_range(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that search_commits rejects limit > 50."""
        tool = git_tools["search_commits"]
        result = await tool(query="test", limit=51)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Limit.*out of range", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_search_commits_limit_negative(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that search_commits rejects negative limit."""
        tool = git_tools["search_commits"]
        result = await tool(query="test", limit=-1)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Limit.*out of range", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_search_commits_since_invalid_format(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that search_commits rejects invalid date format."""
        tool = git_tools["search_commits"]
        result = await tool(query="test", since="not-a-date")
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Invalid date format", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_search_commits_limit_at_boundary_lower(
        self, git_tools: dict[str, Any], mock_git_analyzer: Any
    ) -> None:
        """Test that search_commits accepts limit = 1."""
        mock_git_analyzer.search_commits.return_value = []
        tool = git_tools["search_commits"]
        result = await tool(query="test", limit=1)
        assert "results" in result

    @pytest.mark.asyncio
    async def test_search_commits_limit_at_boundary_upper(
        self, git_tools: dict[str, Any], mock_git_analyzer: Any
    ) -> None:
        """Test that search_commits accepts limit = 50."""
        mock_git_analyzer.search_commits.return_value = []
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
        result = await tool(path="src/main.py", limit=0)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Limit.*out of range", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_get_file_history_limit_above_range(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that get_file_history rejects limit > 500."""
        tool = git_tools["get_file_history"]
        result = await tool(path="src/main.py", limit=501)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Limit.*out of range", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_get_file_history_limit_at_boundary_lower(
        self, git_tools: dict[str, Any], mock_git_analyzer: Any
    ) -> None:
        """Test that get_file_history accepts limit = 1."""
        mock_git_analyzer.git_reader.get_file_history.return_value = []
        tool = git_tools["get_file_history"]
        result = await tool(path="src/main.py", limit=1)
        assert "commits" in result

    @pytest.mark.asyncio
    async def test_get_file_history_limit_at_boundary_upper(
        self, git_tools: dict[str, Any], mock_git_analyzer: Any
    ) -> None:
        """Test that get_file_history accepts limit = 500."""
        mock_git_analyzer.git_reader.get_file_history.return_value = []
        tool = git_tools["get_file_history"]
        result = await tool(path="src/main.py", limit=500)
        assert "commits" in result

    @pytest.mark.asyncio
    async def test_get_file_history_file_not_found(
        self, git_tools: dict[str, Any], mock_git_analyzer: Any
    ) -> None:
        """Test that get_file_history reports file not found."""
        mock_git_analyzer.git_reader.get_file_history.side_effect = (
            FileNotFoundError("File not found")
        )
        tool = git_tools["get_file_history"]
        result = await tool(path="nonexistent/file.py")
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"File not found", result["error"]["message"])
class TestGetChurnHotspotsValidation:
    """Validation tests for get_churn_hotspots tool."""

    @pytest.mark.asyncio
    async def test_get_churn_hotspots_days_below_range(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that get_churn_hotspots rejects days < 1."""
        tool = git_tools["get_churn_hotspots"]
        result = await tool(days=0)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Days.*out of range", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_get_churn_hotspots_days_above_range(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that get_churn_hotspots rejects days > 365."""
        tool = git_tools["get_churn_hotspots"]
        result = await tool(days=366)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Days.*out of range", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_get_churn_hotspots_days_negative(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that get_churn_hotspots rejects negative days."""
        tool = git_tools["get_churn_hotspots"]
        result = await tool(days=-1)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Days.*out of range", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_get_churn_hotspots_limit_below_range(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that get_churn_hotspots rejects limit < 1."""
        tool = git_tools["get_churn_hotspots"]
        result = await tool(limit=0)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Limit.*out of range", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_get_churn_hotspots_limit_above_range(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Test that get_churn_hotspots rejects limit > 50."""
        tool = git_tools["get_churn_hotspots"]
        result = await tool(limit=51)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Limit.*out of range", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_get_churn_hotspots_days_at_boundary_lower(
        self, git_tools: dict[str, Any], mock_git_analyzer: Any
    ) -> None:
        """Test that get_churn_hotspots accepts days = 1."""
        mock_git_analyzer.get_churn_hotspots.return_value = []
        tool = git_tools["get_churn_hotspots"]
        result = await tool(days=1)
        assert "hotspots" in result

    @pytest.mark.asyncio
    async def test_get_churn_hotspots_days_at_boundary_upper(
        self, git_tools: dict[str, Any], mock_git_analyzer: Any
    ) -> None:
        """Test that get_churn_hotspots accepts days = 365."""
        mock_git_analyzer.get_churn_hotspots.return_value = []
        tool = git_tools["get_churn_hotspots"]
        result = await tool(days=365)
        assert "hotspots" in result


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
        self, git_tools: dict[str, Any], mock_git_analyzer: Any
    ) -> None:
        """Test that get_code_authors reports file not found."""
        mock_git_analyzer.get_file_authors.side_effect = (
            FileNotFoundError("File not found")
        )
        tool = git_tools["get_code_authors"]
        result = await tool(path="nonexistent/file.py")
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"File not found", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_get_code_authors_valid_path(
        self, git_tools: dict[str, Any], mock_git_analyzer: Any
    ) -> None:
        """Test that get_code_authors accepts valid path."""
        mock_git_analyzer.get_file_authors.return_value = []
        tool = git_tools["get_code_authors"]
        result = await tool(path="src/main.py")
        assert "authors" in result


# ============================================================================
# SPEC-057: New validation tests
# ============================================================================


class TestIndexCommitsLimitMaxValidation:
    """SPEC-057: index_commits limit upper bound validation tests."""

    @pytest.mark.asyncio
    async def test_limit_exceeds_maximum(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Limit exceeding 100,000 should error."""
        tool = git_tools["index_commits"]
        result = await tool(limit=100_001)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"exceeds maximum", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_limit_at_maximum(
        self, git_tools: dict[str, Any], mock_git_analyzer: Any
    ) -> None:
        """Limit at exactly 100,000 should be accepted."""
        mock_stats = MagicMock()
        mock_stats.commits_indexed = 0
        mock_stats.commits_skipped = 0
        mock_stats.duration_ms = 1
        mock_stats.errors = []
        mock_git_analyzer.index_commits.return_value = mock_stats

        tool = git_tools["index_commits"]
        result = await tool(limit=100_000)
        assert "commits_indexed" in result


class TestSearchCommitsQueryLengthValidation:
    """SPEC-057: Query string length validation tests for search_commits."""

    @pytest.mark.asyncio
    async def test_query_too_long(self, git_tools: dict[str, Any]) -> None:
        """Query exceeding 10,000 chars should error."""
        tool = git_tools["search_commits"]
        result = await tool(query="x" * 10_001)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"too long", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_query_at_max_length(
        self, git_tools: dict[str, Any], mock_git_analyzer: Any
    ) -> None:
        """Query at exactly 10,000 chars should be accepted."""
        mock_git_analyzer.search_commits.return_value = []
        tool = git_tools["search_commits"]
        # Should not raise ValidationError
        result = await tool(query="x" * 10_000)
        assert "results" in result

    @pytest.mark.asyncio
    async def test_query_length_error_shows_limits(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Error should show actual and maximum length."""
        tool = git_tools["search_commits"]
        result = await tool(query="x" * 10_001)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "10001" in result["error"]["message"]
class TestSearchCommitsAuthorValidation:
    """SPEC-057: Author name validation tests for search_commits."""

    @pytest.mark.asyncio
    async def test_author_too_long(self, git_tools: dict[str, Any]) -> None:
        """Author name exceeding 200 chars should error."""
        tool = git_tools["search_commits"]
        result = await tool(query="test", author="x" * 201)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Author name too long", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_author_at_max_length(
        self, git_tools: dict[str, Any], mock_git_analyzer: Any
    ) -> None:
        """Author name at exactly 200 chars should be accepted."""
        mock_git_analyzer.search_commits.return_value = []
        tool = git_tools["search_commits"]
        result = await tool(query="test", author="x" * 200)
        assert "results" in result

    @pytest.mark.asyncio
    async def test_none_author_accepted(
        self, git_tools: dict[str, Any], mock_git_analyzer: Any
    ) -> None:
        """None author should be accepted (no filter)."""
        mock_git_analyzer.search_commits.return_value = []
        tool = git_tools["search_commits"]
        result = await tool(query="test", author=None)
        assert "results" in result

    @pytest.mark.asyncio
    async def test_valid_author_accepted(
        self, git_tools: dict[str, Any], mock_git_analyzer: Any
    ) -> None:
        """Valid author name should be accepted."""
        mock_git_analyzer.search_commits.return_value = []
        tool = git_tools["search_commits"]
        result = await tool(query="test", author="John Doe")
        assert "results" in result

    @pytest.mark.asyncio
    async def test_author_length_error_shows_limits(
        self, git_tools: dict[str, Any]
    ) -> None:
        """Error should show actual and maximum length."""
        tool = git_tools["search_commits"]
        result = await tool(query="test", author="x" * 250)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert "250" in result["error"]["message"]
