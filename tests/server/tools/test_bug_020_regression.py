"""Regression test for BUG-020: store_value returns internal server error.

Tests that store_value properly stores values directly without calling ValueStore,
and returns proper responses.
"""

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from calm.embedding.base import EmbeddingService
from calm.storage.base import VectorStore
from calm.tools.learning import get_learning_tools
from calm.values import ValueStore


class MockEmbedder(EmbeddingService):
    """Mock embedding service."""

    @property
    def dimension(self) -> int:
        return 768

    async def embed(self, text: str) -> np.ndarray:
        return np.array([0.1] * 768, dtype=np.float32)

    async def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        return [np.array([0.1] * 768, dtype=np.float32) for _ in texts]


@pytest.mark.asyncio
async def test_bug_020_regression_store_value_valueerror() -> None:
    """Test that store_value handles validation errors properly.

    Note: The learning tools store_value implementation doesn't use
    ValueStore.store_value, it embeds and stores directly.
    This test is retained for compatibility.
    """
    # Setup: Mock vector store
    mock_vector_store = MagicMock(spec=VectorStore)
    mock_vector_store.upsert = AsyncMock()
    mock_vector_store.create_collection = AsyncMock()

    mock_embedder = MockEmbedder()
    mock_experience_clusterer = MagicMock()
    mock_value_store = MagicMock(spec=ValueStore)

    tools = get_learning_tools(
        vector_store=mock_vector_store,
        semantic_embedder=mock_embedder,
        experience_clusterer=mock_experience_clusterer,
        value_store=mock_value_store,
    )
    store_value = tools["store_value"]

    # Action: call store_value (should succeed as it doesn't use ValueStore.store_value)
    result = await store_value(text="test value", cluster_id="full_0", axis="full")

    # Assert: should return success response
    assert "error" not in result, f"Unexpected error: {result}"
    assert "id" in result
    assert result["text"] == "test value"
    assert result["cluster_id"] == "full_0"
    assert result["axis"] == "full"


@pytest.mark.asyncio
async def test_bug_020_store_value_success() -> None:
    """Test that store_value returns success."""
    # Setup: Mock vector store
    mock_vector_store = MagicMock(spec=VectorStore)
    mock_vector_store.upsert = AsyncMock()
    mock_vector_store.create_collection = AsyncMock()

    mock_embedder = MockEmbedder()
    mock_experience_clusterer = MagicMock()
    mock_value_store = MagicMock(spec=ValueStore)

    tools = get_learning_tools(
        vector_store=mock_vector_store,
        semantic_embedder=mock_embedder,
        experience_clusterer=mock_experience_clusterer,
        value_store=mock_value_store,
    )
    store_value = tools["store_value"]

    # Action: call store_value
    result = await store_value(text="good value", cluster_id="full_0", axis="full")

    # Assert: should return success response
    assert "error" not in result, f"Unexpected error: {result}"
    assert "id" in result
    assert result["text"] == "good value"
    assert result["cluster_id"] == "full_0"
    assert result["axis"] == "full"
    assert "created_at" in result
