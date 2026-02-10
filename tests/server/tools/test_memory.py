"""Tests for memory MCP tools."""

import re
from uuid import UUID

import pytest

from calm.tools.memory import get_memory_tools


@pytest.mark.asyncio
async def test_store_memory_success(mock_services):
    """Test successful memory storage."""
    tools = get_memory_tools(mock_services.vector_store, mock_services.semantic_embedder)
    store_memory = tools["store_memory"]

    result = await store_memory(
        content="Test memory",
        category="fact",
        importance=0.8,
        tags=["test"],
    )

    # Verify result structure - response contains confirmation only, not content
    # Content is only needed on retrieval, not on store confirmation
    assert "id" in result
    assert UUID(result["id"])  # Valid UUID
    assert result["status"] == "stored"
    assert result["category"] == "fact"
    assert result["importance"] == 0.8
    assert "created_at" in result
    # Response should NOT include content (token efficiency)
    assert "content" not in result

    # Verify service calls
    mock_services.semantic_embedder.embed.assert_called_once_with("Test memory")
    mock_services.vector_store.upsert.assert_called_once()


@pytest.mark.asyncio
async def test_store_memory_invalid_category(mock_services):
    """Test validation error for invalid category."""
    tools = get_memory_tools(mock_services.vector_store, mock_services.semantic_embedder)
    store_memory = tools["store_memory"]

    result = await store_memory(content="Test", category="invalid")
    assert "error" in result
    assert result["error"]["type"] == "validation_error"
    assert re.search(r"Invalid category", result["error"]["message"])
@pytest.mark.asyncio
async def test_store_memory_content_too_long(mock_services):
    """Test validation error for content that's too long (no silent truncation)."""
    tools = get_memory_tools(mock_services.vector_store, mock_services.semantic_embedder)
    store_memory = tools["store_memory"]

    long_content = "x" * 15_000
    result = await store_memory(content=long_content, category="fact")
    assert "error" in result
    assert result["error"]["type"] == "validation_error"
    assert re.search(r"Content too long", result["error"]["message"])
@pytest.mark.asyncio
async def test_store_memory_importance_out_of_range(mock_services):
    """Test validation error for importance out of range (no silent clamping)."""
    tools = get_memory_tools(mock_services.vector_store, mock_services.semantic_embedder)
    store_memory = tools["store_memory"]

    result = await store_memory(content="Test", category="fact", importance=1.5)
    assert "error" in result
    assert result["error"]["type"] == "validation_error"
    assert re.search(r"Importance.*out of range", result["error"]["message"])
    result = await store_memory(content="Test", category="fact", importance=-0.1)
    assert "error" in result
    assert result["error"]["type"] == "validation_error"
    assert re.search(r"Importance.*out of range", result["error"]["message"])
@pytest.mark.asyncio
async def test_store_memory_default_values(mock_services):
    """Test store_memory with default values."""
    tools = get_memory_tools(mock_services.vector_store, mock_services.semantic_embedder)
    store_memory = tools["store_memory"]

    result = await store_memory(content="Test", category="fact")

    assert result["importance"] == 0.5  # Default
    # Note: tags are not included in the response (token efficiency)


@pytest.mark.asyncio
async def test_retrieve_memories_success(mock_services, mock_search_result):
    """Test successful memory retrieval."""
    tools = get_memory_tools(mock_services.vector_store, mock_services.semantic_embedder)
    retrieve_memories = tools["retrieve_memories"]

    # Mock search results
    mock_result = mock_search_result()
    mock_services.vector_store.search.return_value = [mock_result]

    result = await retrieve_memories(query="test query", limit=10)

    assert result["count"] == 1
    assert result["results"][0]["score"] == 0.95
    assert result["results"][0]["content"] == "Test content"

    # Verify service calls
    mock_services.semantic_embedder.embed.assert_called_once_with("test query")
    mock_services.vector_store.search.assert_called_once()


@pytest.mark.asyncio
async def test_retrieve_memories_empty_query(mock_services):
    """Test empty query returns empty results."""
    tools = get_memory_tools(mock_services.vector_store, mock_services.semantic_embedder)
    retrieve_memories = tools["retrieve_memories"]

    result = await retrieve_memories(query="   ", limit=10)

    assert result["count"] == 0
    assert result["results"] == []
    mock_services.semantic_embedder.embed.assert_not_called()


@pytest.mark.asyncio
async def test_retrieve_memories_with_filters(mock_services):
    """Test retrieve with category and importance filters."""
    tools = get_memory_tools(mock_services.vector_store, mock_services.semantic_embedder)
    retrieve_memories = tools["retrieve_memories"]

    await retrieve_memories(
        query="test",
        category="fact",
        min_importance=0.7,
        limit=5,
    )

    # Check that filters were passed to search
    call_args = mock_services.vector_store.search.call_args
    filters = call_args.kwargs["filters"]
    assert filters["category"] == "fact"
    assert filters["importance"] == {"$gte": 0.7}


@pytest.mark.asyncio
async def test_retrieve_memories_invalid_category(mock_services):
    """Test validation error for invalid category."""
    tools = get_memory_tools(mock_services.vector_store, mock_services.semantic_embedder)
    retrieve_memories = tools["retrieve_memories"]

    result = await retrieve_memories(query="test", category="invalid")
    assert "error" in result
    assert result["error"]["type"] == "validation_error"
    assert re.search(r"Invalid category", result["error"]["message"])
@pytest.mark.asyncio
async def test_retrieve_memories_limit_validation(mock_services):
    """Test limit validation."""
    tools = get_memory_tools(mock_services.vector_store, mock_services.semantic_embedder)
    retrieve_memories = tools["retrieve_memories"]

    # Too small
    result = await retrieve_memories(query="test", limit=0)
    assert "error" in result
    assert result["error"]["type"] == "validation_error"
    assert re.search(r"Limit.*out of range", result["error"]["message"])
    # Too large
    result = await retrieve_memories(query="test", limit=101)
    assert "error" in result
    assert result["error"]["type"] == "validation_error"
    assert re.search(r"Limit.*out of range", result["error"]["message"])
@pytest.mark.asyncio
async def test_list_memories_success(mock_services, mock_search_result):
    """Test successful memory listing."""
    tools = get_memory_tools(mock_services.vector_store, mock_services.semantic_embedder)
    list_memories = tools["list_memories"]

    # Mock scroll and count
    mock_result = mock_search_result()
    mock_services.vector_store.scroll.return_value = [mock_result]
    mock_services.vector_store.count.return_value = 1

    result = await list_memories(limit=10)

    assert result["count"] == 1
    assert result["total"] == 1
    assert len(result["results"]) == 1


@pytest.mark.asyncio
async def test_list_memories_pagination(mock_services, mock_search_result):
    """Test pagination with offset."""
    tools = get_memory_tools(mock_services.vector_store, mock_services.semantic_embedder)
    list_memories = tools["list_memories"]

    # Create multiple results
    results = [
        mock_search_result(
            id=f"id-{i}", payload={"created_at": f"2025-01-0{i}T00:00:00Z"}
        )
        for i in range(5)
    ]
    mock_services.vector_store.scroll.return_value = results
    mock_services.vector_store.count.return_value = 5

    # Get second page
    result = await list_memories(limit=2, offset=2)

    # Should return 2 results (items 2 and 3)
    assert result["count"] == 2
    assert result["total"] == 5


@pytest.mark.asyncio
async def test_list_memories_with_filters(mock_services):
    """Test listing with category and tag filters."""
    tools = get_memory_tools(mock_services.vector_store, mock_services.semantic_embedder)
    list_memories = tools["list_memories"]

    await list_memories(category="fact", tags=["important", "work"])

    # Check filters
    call_args = mock_services.vector_store.scroll.call_args
    filters = call_args.kwargs["filters"]
    assert filters["category"] == "fact"
    assert filters["tags"] == {"$in": ["important", "work"]}


@pytest.mark.asyncio
async def test_list_memories_invalid_offset(mock_services):
    """Test validation error for negative offset."""
    tools = get_memory_tools(mock_services.vector_store, mock_services.semantic_embedder)
    list_memories = tools["list_memories"]

    result = await list_memories(offset=-1)
    assert "error" in result
    assert result["error"]["type"] == "validation_error"
    assert re.search(r"Offset.*must be >= 0", result["error"]["message"])
@pytest.mark.asyncio
async def test_list_memories_limit_validation(mock_services):
    """Test limit validation."""
    tools = get_memory_tools(mock_services.vector_store, mock_services.semantic_embedder)
    list_memories = tools["list_memories"]

    result = await list_memories(limit=0)
    assert "error" in result
    assert result["error"]["type"] == "validation_error"
    assert re.search(r"Limit.*out of range", result["error"]["message"])
    result = await list_memories(limit=201)
    assert "error" in result
    assert result["error"]["type"] == "validation_error"
    assert re.search(r"Limit.*out of range", result["error"]["message"])
@pytest.mark.asyncio
async def test_delete_memory_success(mock_services):
    """Test successful memory deletion."""
    tools = get_memory_tools(mock_services.vector_store, mock_services.semantic_embedder)
    delete_memory = tools["delete_memory"]

    test_uuid = "12345678-1234-1234-1234-123456789abc"
    result = await delete_memory(memory_id=test_uuid)

    assert result["deleted"] is True
    mock_services.vector_store.delete.assert_called_once_with(
        collection="memories",
        id=test_uuid,
    )


@pytest.mark.asyncio
async def test_delete_memory_not_found(mock_services):
    """Test delete returns false on failure (not an error)."""
    tools = get_memory_tools(mock_services.vector_store, mock_services.semantic_embedder)
    delete_memory = tools["delete_memory"]

    # Make delete raise an exception
    mock_services.vector_store.delete.side_effect = Exception("Not found")

    # SPEC-057: memory_id must be valid UUID format
    result = await delete_memory(memory_id="00000000-0000-0000-0000-000000000000")

    assert result["deleted"] is False


@pytest.mark.asyncio
async def test_all_valid_categories_accepted(mock_services):
    """Test that all valid categories are accepted."""
    tools = get_memory_tools(mock_services.vector_store, mock_services.semantic_embedder)
    store_memory = tools["store_memory"]

    valid_categories = [
        "preference",
        "fact",
        "event",
        "workflow",
        "context",
        "error",
        "decision",
    ]

    for category in valid_categories:
        result = await store_memory(content="Test", category=category)
        assert result["category"] == category
