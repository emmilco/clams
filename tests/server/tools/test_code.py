"""Tests for code MCP tools."""

from unittest.mock import Mock

import pytest

from calm.tools.code import get_code_tools
from calm.tools.validation import ValidationError


@pytest.mark.asyncio
async def test_index_codebase_not_available(mock_services):
    """Test that code tools return helpful message when CodeIndexer unavailable."""
    tools = get_code_tools(mock_services.vector_store, mock_services.code_embedder)
    index_codebase = tools["index_codebase"]

    result = await index_codebase(directory="/tmp", project="test")

    assert result["status"] == "not_available"


@pytest.mark.asyncio
async def test_search_code_empty_query(mock_services):
    """Test that empty query returns empty results."""
    # Add mock code indexer
    mock_services.code_indexer = Mock()

    tools = get_code_tools(
        mock_services.vector_store, mock_services.code_embedder,
        code_indexer=mock_services.code_indexer,
    )
    search_code = tools["search_code"]

    result = await search_code(query="   ")

    assert result["count"] == 0
    assert result["results"] == []


@pytest.mark.asyncio
async def test_search_code_limit_validation(mock_services):
    """Test limit validation for search_code."""
    mock_services.code_indexer = Mock()

    tools = get_code_tools(
        mock_services.vector_store, mock_services.code_embedder,
        code_indexer=mock_services.code_indexer,
    )
    search_code = tools["search_code"]

    with pytest.raises(ValidationError, match="Limit.*out of range"):
        await search_code(query="test", limit=0)

    with pytest.raises(ValidationError, match="Limit.*out of range"):
        await search_code(query="test", limit=51)


@pytest.mark.asyncio
async def test_find_similar_code_snippet_too_long(mock_services):
    """Test validation for snippet that's too long (no silent truncation)."""
    mock_services.code_indexer = Mock()

    tools = get_code_tools(
        mock_services.vector_store, mock_services.code_embedder,
        code_indexer=mock_services.code_indexer,
    )
    find_similar_code = tools["find_similar_code"]

    long_snippet = "x" * 6000
    with pytest.raises(ValidationError, match="Snippet too long"):
        await find_similar_code(snippet=long_snippet)


@pytest.mark.asyncio
async def test_find_similar_code_empty_snippet(mock_services):
    """Test that empty snippet returns empty results."""
    mock_services.code_indexer = Mock()

    tools = get_code_tools(
        mock_services.vector_store, mock_services.code_embedder,
        code_indexer=mock_services.code_indexer,
    )
    find_similar_code = tools["find_similar_code"]

    result = await find_similar_code(snippet="   ")

    assert result["count"] == 0
    assert result["results"] == []


@pytest.mark.asyncio
async def test_find_similar_code_limit_validation(mock_services):
    """Test limit validation for find_similar_code."""
    mock_services.code_indexer = Mock()

    tools = get_code_tools(
        mock_services.vector_store, mock_services.code_embedder,
        code_indexer=mock_services.code_indexer,
    )
    find_similar_code = tools["find_similar_code"]

    with pytest.raises(ValidationError, match="Limit.*out of range"):
        await find_similar_code(snippet="test", limit=0)

    with pytest.raises(ValidationError, match="Limit.*out of range"):
        await find_similar_code(snippet="test", limit=51)


@pytest.mark.asyncio
async def test_index_codebase_directory_not_found(mock_services, tmp_path):
    """Test validation error when directory doesn't exist."""
    mock_services.code_indexer = Mock()

    tools = get_code_tools(
        mock_services.vector_store, mock_services.code_embedder,
        code_indexer=mock_services.code_indexer,
    )
    index_codebase = tools["index_codebase"]

    with pytest.raises(ValidationError, match="Directory not found"):
        await index_codebase(
            directory=str(tmp_path / "nonexistent"),
            project="test",
        )


@pytest.mark.asyncio
async def test_index_codebase_not_a_directory(mock_services, tmp_path):
    """Test validation error when path is not a directory."""
    mock_services.code_indexer = Mock()

    # Create a file, not a directory
    test_file = tmp_path / "test.txt"
    test_file.write_text("test")

    tools = get_code_tools(
        mock_services.vector_store, mock_services.code_embedder,
        code_indexer=mock_services.code_indexer,
    )
    index_codebase = tools["index_codebase"]

    with pytest.raises(ValidationError, match="Not a directory"):
        await index_codebase(directory=str(test_file), project="test")


@pytest.mark.asyncio
async def test_search_code_with_filters(mock_services, mock_search_result):
    """Test search_code with project and language filters."""
    mock_services.code_indexer = Mock()

    tools = get_code_tools(
        mock_services.vector_store, mock_services.code_embedder,
        code_indexer=mock_services.code_indexer,
    )
    search_code = tools["search_code"]

    # Mock search results
    mock_result = mock_search_result(
        payload={
            "id": "code-1",
            "project": "test-project",
            "language": "python",
            "name": "test_function",
        }
    )
    mock_services.vector_store.search.return_value = [mock_result]

    result = await search_code(
        query="test function",
        project="test-project",
        language="Python",
        limit=5,
    )

    # Verify filters were applied
    call_args = mock_services.vector_store.search.call_args
    filters = call_args.kwargs["filters"]
    assert filters["project"] == "test-project"
    assert filters["language"] == "python"  # Should be lowercased

    # Verify results
    assert result["count"] == 1
    assert result["results"][0]["name"] == "test_function"


@pytest.mark.asyncio
async def test_find_similar_code_with_project_filter(mock_services):
    """Test find_similar_code with project filter."""
    mock_services.code_indexer = Mock()

    tools = get_code_tools(
        mock_services.vector_store, mock_services.code_embedder,
        code_indexer=mock_services.code_indexer,
    )
    find_similar_code = tools["find_similar_code"]

    mock_services.vector_store.search.return_value = []

    await find_similar_code(snippet="def test(): pass", project="my-project")

    # Verify filter was applied
    call_args = mock_services.vector_store.search.call_args
    filters = call_args.kwargs["filters"]
    assert filters == {"project": "my-project"}
