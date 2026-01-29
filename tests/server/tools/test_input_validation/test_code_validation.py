"""Input validation tests for code tools.

Tests cover:
- index_codebase: directory, project, recursive
- search_code: query, project, language, limit
- find_similar_code: snippet, project, limit

SPEC-057 additions:
- search_code: language validation with helpful error
- index_codebase: project format validation (alphanumeric, dashes, underscores, max 100 chars)

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


# ============================================================================
# SPEC-057: New validation tests
# ============================================================================


class TestSearchCodeLanguageValidation:
    """SPEC-057: Language validation tests for search_code."""

    @pytest.mark.asyncio
    async def test_invalid_language(self, code_tools: dict[str, Any]) -> None:
        """Unsupported language should error."""
        tool = code_tools["search_code"]
        with pytest.raises(ValidationError, match="Unsupported language"):
            await tool(query="test", language="brainfuck")

    @pytest.mark.asyncio
    async def test_invalid_language_lists_supported(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Error message should list supported languages."""
        tool = code_tools["search_code"]
        with pytest.raises(ValidationError) as exc_info:
            await tool(query="test", language="invalid")
        assert "python" in str(exc_info.value)
        assert "typescript" in str(exc_info.value)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("language", ["python", "Python", "PYTHON"])
    async def test_valid_language_case_insensitive(
        self, code_tools: dict[str, Any], language: str
    ) -> None:
        """Language validation should be case-insensitive."""
        tool = code_tools["search_code"]
        # Should not raise
        result = await tool(query="test", language=language)
        assert "results" in result

    @pytest.mark.asyncio
    async def test_none_language_accepted(self, code_tools: dict[str, Any]) -> None:
        """None language should be accepted (no filter)."""
        tool = code_tools["search_code"]
        result = await tool(query="test", language=None)
        assert "results" in result

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "language",
        [
            "python",
            "typescript",
            "javascript",
            "rust",
            "go",
            "java",
            "c",
            "cpp",
            "csharp",
            "ruby",
            "php",
            "swift",
            "kotlin",
            "scala",
        ],
    )
    async def test_all_supported_languages(
        self, code_tools: dict[str, Any], language: str
    ) -> None:
        """All documented languages should be accepted."""
        tool = code_tools["search_code"]
        result = await tool(query="test", language=language)
        assert "results" in result


class TestIndexCodebaseProjectValidation:
    """SPEC-057: Project identifier format validation tests."""

    @pytest.mark.asyncio
    async def test_project_with_spaces(
        self, code_tools: dict[str, Any], tmp_path: Any
    ) -> None:
        """Project with spaces should error."""
        tool = code_tools["index_codebase"]
        with pytest.raises(ValidationError, match="Invalid project identifier"):
            await tool(directory=str(tmp_path), project="has spaces")

    @pytest.mark.asyncio
    async def test_project_with_special_chars(
        self, code_tools: dict[str, Any], tmp_path: Any
    ) -> None:
        """Project with special chars should error."""
        tool = code_tools["index_codebase"]
        with pytest.raises(ValidationError, match="Invalid project identifier"):
            await tool(directory=str(tmp_path), project="has@special!")

    @pytest.mark.asyncio
    async def test_project_too_long(
        self, code_tools: dict[str, Any], tmp_path: Any
    ) -> None:
        """Project > 100 chars should error."""
        tool = code_tools["index_codebase"]
        with pytest.raises(ValidationError, match="too long"):
            await tool(directory=str(tmp_path), project="x" * 101)

    @pytest.mark.asyncio
    async def test_project_empty(
        self, code_tools: dict[str, Any], tmp_path: Any
    ) -> None:
        """Empty project should error."""
        tool = code_tools["index_codebase"]
        with pytest.raises(ValidationError, match="cannot be empty"):
            await tool(directory=str(tmp_path), project="")

    @pytest.mark.asyncio
    async def test_project_starts_with_dash(
        self, code_tools: dict[str, Any], tmp_path: Any
    ) -> None:
        """Project starting with dash should error."""
        tool = code_tools["index_codebase"]
        with pytest.raises(ValidationError, match="Invalid project identifier"):
            await tool(directory=str(tmp_path), project="-starts-with-dash")

    @pytest.mark.asyncio
    async def test_valid_project_identifiers(
        self, code_tools: dict[str, Any], mock_services: Any, tmp_path: Any
    ) -> None:
        """Valid project formats should be accepted."""
        mock_stats = MagicMock()
        mock_stats.files_indexed = 0
        mock_stats.units_indexed = 0
        mock_stats.files_skipped = 0
        mock_stats.errors = []
        mock_stats.duration_ms = 1
        mock_services.code_indexer.index_directory.return_value = mock_stats

        tool = code_tools["index_codebase"]
        # All these should be accepted
        for project in ["my-project", "my_project", "MyProject123", "test", "a"]:
            result = await tool(directory=str(tmp_path), project=project)
            assert result["project"] == project

    @pytest.mark.asyncio
    async def test_project_at_max_length(
        self, code_tools: dict[str, Any], mock_services: Any, tmp_path: Any
    ) -> None:
        """Project at exactly 100 chars should be accepted."""
        mock_stats = MagicMock()
        mock_stats.files_indexed = 0
        mock_stats.units_indexed = 0
        mock_stats.files_skipped = 0
        mock_stats.errors = []
        mock_stats.duration_ms = 1
        mock_services.code_indexer.index_directory.return_value = mock_stats

        tool = code_tools["index_codebase"]
        result = await tool(directory=str(tmp_path), project="x" * 100)
        assert result["project"] == "x" * 100


class TestSearchCodeQueryLengthValidation:
    """SPEC-057: Query string length validation tests for search_code."""

    @pytest.mark.asyncio
    async def test_query_too_long(self, code_tools: dict[str, Any]) -> None:
        """Query exceeding 10,000 chars should error."""
        tool = code_tools["search_code"]
        with pytest.raises(ValidationError, match="too long"):
            await tool(query="x" * 10_001)

    @pytest.mark.asyncio
    async def test_query_at_max_length(self, code_tools: dict[str, Any]) -> None:
        """Query at exactly 10,000 chars should be accepted."""
        tool = code_tools["search_code"]
        # Should not raise ValidationError
        result = await tool(query="x" * 10_000)
        assert "results" in result

    @pytest.mark.asyncio
    async def test_query_length_error_shows_limits(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Error should show actual and maximum length."""
        tool = code_tools["search_code"]
        with pytest.raises(ValidationError) as exc_info:
            await tool(query="x" * 10_001)
        assert "10001" in str(exc_info.value)
        assert "10000" in str(exc_info.value)


class TestSearchCodeOptionalProjectValidation:
    """SPEC-057: Optional project filter validation tests for search_code."""

    @pytest.mark.asyncio
    async def test_invalid_project_with_spaces(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Project filter with spaces should error."""
        tool = code_tools["search_code"]
        with pytest.raises(ValidationError, match="Invalid project identifier"):
            await tool(query="test", project="has spaces")

    @pytest.mark.asyncio
    async def test_invalid_project_with_special_chars(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Project filter with special chars should error."""
        tool = code_tools["search_code"]
        with pytest.raises(ValidationError, match="Invalid project identifier"):
            await tool(query="test", project="has@special!")

    @pytest.mark.asyncio
    async def test_none_project_accepted(self, code_tools: dict[str, Any]) -> None:
        """None project should be accepted (no filter)."""
        tool = code_tools["search_code"]
        result = await tool(query="test", project=None)
        assert "results" in result

    @pytest.mark.asyncio
    async def test_valid_project_accepted(self, code_tools: dict[str, Any]) -> None:
        """Valid project identifier should be accepted."""
        tool = code_tools["search_code"]
        result = await tool(query="test", project="my-project")
        assert "results" in result


class TestFindSimilarCodeOptionalProjectValidation:
    """SPEC-057: Optional project filter validation tests for find_similar_code."""

    @pytest.mark.asyncio
    async def test_invalid_project_with_spaces(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Project filter with spaces should error."""
        tool = code_tools["find_similar_code"]
        with pytest.raises(ValidationError, match="Invalid project identifier"):
            await tool(snippet="def foo(): pass", project="has spaces")

    @pytest.mark.asyncio
    async def test_invalid_project_with_special_chars(
        self, code_tools: dict[str, Any]
    ) -> None:
        """Project filter with special chars should error."""
        tool = code_tools["find_similar_code"]
        with pytest.raises(ValidationError, match="Invalid project identifier"):
            await tool(snippet="def foo(): pass", project="has@special!")

    @pytest.mark.asyncio
    async def test_none_project_accepted(self, code_tools: dict[str, Any]) -> None:
        """None project should be accepted (no filter)."""
        tool = code_tools["find_similar_code"]
        result = await tool(snippet="def foo(): pass", project=None)
        assert "results" in result

    @pytest.mark.asyncio
    async def test_valid_project_accepted(self, code_tools: dict[str, Any]) -> None:
        """Valid project identifier should be accepted."""
        tool = code_tools["find_similar_code"]
        result = await tool(snippet="def foo(): pass", project="my-project")
        assert "results" in result
