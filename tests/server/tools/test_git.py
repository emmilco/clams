"""Tests for git MCP tools."""

from unittest.mock import AsyncMock, Mock

import pytest

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
