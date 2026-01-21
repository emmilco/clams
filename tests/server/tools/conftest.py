"""Shared fixtures for MCP tools tests."""

from unittest.mock import AsyncMock

import pytest

from clams.server.tools import ServiceContainer
from clams.storage.base import SearchResult


@pytest.fixture
def mock_code_embedder():
    """Create mock code embedding service."""
    service = AsyncMock()
    service.embed.return_value = [0.1] * 384
    service.embed_batch.return_value = [[0.1] * 384, [0.2] * 384]
    service.dimension = 384
    return service


@pytest.fixture
def mock_semantic_embedder():
    """Create mock semantic embedding service."""
    service = AsyncMock()
    service.embed.return_value = [0.1] * 768
    service.embed_batch.return_value = [[0.1] * 768, [0.2] * 768]
    service.dimension = 768
    return service


@pytest.fixture
def mock_vector_store():
    """Create mock vector store."""
    store = AsyncMock()
    store.upsert.return_value = None
    store.delete.return_value = None
    store.count.return_value = 0
    store.search.return_value = []
    store.scroll.return_value = []
    return store


@pytest.fixture
def mock_metadata_store():
    """Create mock metadata store."""
    store = AsyncMock()
    return store


@pytest.fixture
def mock_services(
    mock_code_embedder, mock_semantic_embedder, mock_vector_store, mock_metadata_store
):
    """Create mock service container with core services."""
    return ServiceContainer(
        code_embedder=mock_code_embedder,
        semantic_embedder=mock_semantic_embedder,
        vector_store=mock_vector_store,
        metadata_store=mock_metadata_store,
        code_indexer=None,
        git_analyzer=None,
        searcher=None,
    )


@pytest.fixture
def mock_search_result():
    """Create a mock search result."""

    def _create(
        id: str = "12345678-1234-1234-1234-123456789abc",
        score: float = 0.95,
        payload: dict | None = None,
    ):
        if payload is None:
            payload = {
                "id": id,
                "content": "Test content",
                "category": "fact",
                "importance": 0.8,
                "tags": [],
                "created_at": "2025-01-01T00:00:00Z",
            }
        return SearchResult(id=id, score=score, payload=payload, vector=None)

    return _create
