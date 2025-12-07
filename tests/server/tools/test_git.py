"""Tests for git MCP tools."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from learning_memory_server.git.base import Commit, IndexingError, IndexingStats
from learning_memory_server.server.errors import MCPError, ValidationError
from learning_memory_server.server.tools.git import get_git_tools


@pytest.mark.asyncio
async def test_search_commits_not_available(mock_services):
    """Test that search_commits returns helpful error when GitAnalyzer unavailable."""
    tools = get_git_tools(mock_services)
    search_commits = tools["search_commits"]

    with pytest.raises(
        MCPError,
        match="Git commit search not available.*GitAnalyzer.*SPEC-002-07",
    ):
        await search_commits(query="test")


@pytest.mark.asyncio
async def test_get_file_history_not_available(mock_services):
    """Test that get_file_history returns helpful error when GitAnalyzer unavailable."""
    tools = get_git_tools(mock_services)
    get_file_history = tools["get_file_history"]

    with pytest.raises(
        MCPError,
        match="Git file history not available.*GitAnalyzer.*SPEC-002-07",
    ):
        await get_file_history(path="test.py")


@pytest.mark.asyncio
async def test_get_churn_hotspots_not_available(mock_services):
    """Test helpful error when GitAnalyzer unavailable for churn hotspots."""
    tools = get_git_tools(mock_services)
    get_churn_hotspots = tools["get_churn_hotspots"]

    with pytest.raises(
        MCPError,
        match="Git churn analysis not available.*GitAnalyzer.*SPEC-002-07",
    ):
        await get_churn_hotspots()


@pytest.mark.asyncio
async def test_get_code_authors_not_available(mock_services):
    """Test that get_code_authors returns helpful error when GitAnalyzer unavailable."""
    tools = get_git_tools(mock_services)
    get_code_authors = tools["get_code_authors"]

    with pytest.raises(
        MCPError,
        match="Git author analysis not available.*GitAnalyzer.*SPEC-002-07",
    ):
        await get_code_authors(path="test.py")


# Tests for when GitAnalyzer IS available


@pytest.mark.asyncio
async def test_search_commits_empty_query(mock_services):
    """Test that empty query returns empty results."""
    mock_services.git_analyzer = Mock()

    tools = get_git_tools(mock_services)
    search_commits = tools["search_commits"]

    result = await search_commits(query="   ")

    assert result["count"] == 0
    assert result["results"] == []


@pytest.mark.asyncio
async def test_search_commits_limit_validation(mock_services):
    """Test limit validation for search_commits."""
    mock_services.git_analyzer = Mock()

    tools = get_git_tools(mock_services)
    search_commits = tools["search_commits"]

    with pytest.raises(ValidationError, match="Limit.*out of range"):
        await search_commits(query="test", limit=0)

    with pytest.raises(ValidationError, match="Limit.*out of range"):
        await search_commits(query="test", limit=51)


@pytest.mark.asyncio
async def test_search_commits_invalid_date_format(mock_services):
    """Test validation error for invalid date format."""
    mock_services.git_analyzer = Mock()

    tools = get_git_tools(mock_services)
    search_commits = tools["search_commits"]

    with pytest.raises(ValidationError, match="Invalid date format"):
        await search_commits(query="test", since="not-a-date")


@pytest.mark.asyncio
async def test_get_file_history_limit_validation(mock_services):
    """Test limit validation for get_file_history."""
    mock_services.git_analyzer = Mock()

    tools = get_git_tools(mock_services)
    get_file_history = tools["get_file_history"]

    with pytest.raises(ValidationError, match="Limit.*out of range"):
        await get_file_history(path="test.py", limit=0)

    with pytest.raises(ValidationError, match="Limit.*out of range"):
        await get_file_history(path="test.py", limit=501)


@pytest.mark.asyncio
async def test_get_file_history_file_not_found(mock_services):
    """Test validation error when file not found in repository."""
    mock_services.git_analyzer = Mock()
    mock_services.git_analyzer.git_reader = Mock()
    mock_services.git_analyzer.git_reader.get_file_history = AsyncMock(
        side_effect=FileNotFoundError("File not found")
    )

    tools = get_git_tools(mock_services)
    get_file_history = tools["get_file_history"]

    with pytest.raises(ValidationError, match="File not found in repository"):
        await get_file_history(path="nonexistent.py")


@pytest.mark.asyncio
async def test_get_churn_hotspots_days_validation(mock_services):
    """Test days validation for get_churn_hotspots."""
    mock_services.git_analyzer = Mock()

    tools = get_git_tools(mock_services)
    get_churn_hotspots = tools["get_churn_hotspots"]

    with pytest.raises(ValidationError, match="Days.*out of range"):
        await get_churn_hotspots(days=0)

    with pytest.raises(ValidationError, match="Days.*out of range"):
        await get_churn_hotspots(days=366)


@pytest.mark.asyncio
async def test_get_churn_hotspots_limit_validation(mock_services):
    """Test limit validation for get_churn_hotspots."""
    mock_services.git_analyzer = Mock()

    tools = get_git_tools(mock_services)
    get_churn_hotspots = tools["get_churn_hotspots"]

    with pytest.raises(ValidationError, match="Limit.*out of range"):
        await get_churn_hotspots(limit=0)

    with pytest.raises(ValidationError, match="Limit.*out of range"):
        await get_churn_hotspots(limit=51)


@pytest.mark.asyncio
async def test_get_code_authors_file_not_found(mock_services):
    """Test validation error when file not found."""
    mock_services.git_analyzer = Mock()
    mock_services.git_analyzer.get_file_authors = AsyncMock(
        side_effect=FileNotFoundError("File not found")
    )

    tools = get_git_tools(mock_services)
    get_code_authors = tools["get_code_authors"]

    with pytest.raises(ValidationError, match="File not found in repository"):
        await get_code_authors(path="nonexistent.py")


# Regression test for BUG-011


@pytest.mark.asyncio
async def test_index_commits_not_available(mock_services):
    """Test that index_commits returns helpful error when GitAnalyzer unavailable."""
    tools = get_git_tools(mock_services)
    index_commits = tools["index_commits"]

    with pytest.raises(
        MCPError,
        match="Git commit indexing not available.*GitAnalyzer",
    ):
        await index_commits()


@pytest.mark.asyncio
async def test_index_commits_invalid_date_format(mock_services):
    """Test validation error for invalid date format in index_commits."""
    mock_services.git_analyzer = Mock()

    tools = get_git_tools(mock_services)
    index_commits = tools["index_commits"]

    with pytest.raises(ValidationError, match="Invalid date format"):
        await index_commits(since="not-a-date")


@pytest.mark.asyncio
async def test_index_commits_invalid_limit(mock_services):
    """Test validation error for invalid limit in index_commits."""
    mock_services.git_analyzer = Mock()

    tools = get_git_tools(mock_services)
    index_commits = tools["index_commits"]

    with pytest.raises(ValidationError, match="Limit must be positive"):
        await index_commits(limit=0)


@pytest.mark.asyncio
async def test_index_and_search_commits_workflow(mock_services):
    """Test that commits must be indexed before they can be searched (BUG-011 regression test).

    This test verifies the fix for BUG-011, where search_commits returned empty results
    because the index_commits tool was missing. Users must call index_commits to populate
    the vector store before search_commits can find results.
    """
    # Setup: Create git analyzer with mock methods
    mock_services.git_analyzer = Mock()

    # Mock search_commits to return empty before indexing
    mock_services.git_analyzer.search_commits = AsyncMock(return_value=[])

    tools = get_git_tools(mock_services)
    search_commits = tools["search_commits"]
    index_commits = tools["index_commits"]

    # 1. Search before indexing - should return empty
    results_before = await search_commits(query="test", limit=5)
    assert results_before["count"] == 0
    assert results_before["results"] == []

    # 2. Index commits
    mock_stats = IndexingStats(
        commits_indexed=10,
        commits_skipped=0,
        duration_ms=500,
        errors=[],
    )
    mock_services.git_analyzer.index_commits = AsyncMock(return_value=mock_stats)

    index_result = await index_commits(force=True)
    assert index_result["commits_indexed"] == 10
    assert index_result["commits_skipped"] == 0
    assert index_result["duration_ms"] == 500
    assert index_result["errors"] == []

    # 3. Search after indexing - should find results
    mock_commit = Commit(
        sha="abc123",
        message="Add test feature",
        author="Test Author",
        author_email="test@example.com",
        timestamp=datetime(2025, 1, 1, 12, 0, 0),
        files_changed=["test.py"],
        insertions=10,
        deletions=5,
    )
    # Add score attribute dynamically (as done by search results)
    mock_commit.score = 0.95  # type: ignore[attr-defined]

    mock_services.git_analyzer.search_commits = AsyncMock(return_value=[mock_commit])

    results_after = await search_commits(query="test", limit=5)
    assert results_after["count"] == 1
    assert len(results_after["results"]) == 1

    # Verify result structure
    result = results_after["results"][0]
    assert result["sha"] == "abc123"
    assert result["message"] == "Add test feature"
    assert result["author"] == "Test Author"
    assert result["author_email"] == "test@example.com"
    assert result["score"] == 0.95


@pytest.mark.asyncio
async def test_index_commits_with_errors(mock_services):
    """Test that index_commits reports errors encountered during indexing."""
    mock_services.git_analyzer = Mock()

    # Mock stats with errors
    mock_error = IndexingError(
        sha="bad123",
        error_type="embedding_failed",
        message="Failed to embed commit",
    )
    mock_stats = IndexingStats(
        commits_indexed=8,
        commits_skipped=2,
        duration_ms=300,
        errors=[mock_error],
    )
    mock_services.git_analyzer.index_commits = AsyncMock(return_value=mock_stats)

    tools = get_git_tools(mock_services)
    index_commits = tools["index_commits"]

    result = await index_commits(force=True)

    assert result["commits_indexed"] == 8
    assert result["commits_skipped"] == 2
    assert len(result["errors"]) == 1
    assert result["errors"][0]["sha"] == "bad123"
    assert result["errors"][0]["error_type"] == "embedding_failed"
    assert result["errors"][0]["message"] == "Failed to embed commit"
