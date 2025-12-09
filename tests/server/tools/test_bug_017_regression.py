"""Regression test for BUG-017: get_clusters returns internal server error.

Tests that get_clusters returns InsufficientDataError (not internal_error)
when GHAP collections don't exist.
"""

import numpy as np
import pytest

from clams.clustering import Clusterer, ExperienceClusterer
from clams.embedding.base import EmbeddingService
from clams.server.tools.learning import get_learning_tools
from clams.storage.qdrant import QdrantVectorStore
from clams.values import ValueStore


class MockEmbedder(EmbeddingService):
    """Mock embedding service for testing."""

    @property
    def dimension(self) -> int:
        return 768

    async def embed(self, text: str) -> np.ndarray:
        return np.array([0.1] * 768, dtype=np.float32)

    async def embed_batch(self, texts: list[str]) -> np.ndarray:
        return np.array([[0.1] * 768 for _ in texts], dtype=np.float32)


@pytest.mark.asyncio
async def test_bug_017_regression_get_clusters_no_collection() -> None:
    """Test that get_clusters returns insufficient_data (not internal_error).

    Regression test for BUG-017 where missing GHAP collections caused
    UnexpectedResponse to fall through to generic Exception handler,
    returning "internal_error" instead of "insufficient_data".
    """
    # Setup: in-memory Qdrant with NO collections created
    vector_store = QdrantVectorStore(url=":memory:")
    clusterer = Clusterer()
    experience_clusterer = ExperienceClusterer(
        vector_store=vector_store,
        clusterer=clusterer,
    )

    value_store = ValueStore(
        embedding_service=MockEmbedder(),
        vector_store=vector_store,
        clusterer=experience_clusterer,
    )

    tools = get_learning_tools(experience_clusterer, value_store)
    get_clusters = tools["get_clusters"]

    # Action: call get_clusters on non-existent collection
    result = await get_clusters(axis="full")

    # Assert: should return insufficient_data error, NOT internal_error
    assert "error" in result, "Expected error response"
    assert result["error"]["type"] == "insufficient_data", (
        f"Expected insufficient_data, got {result['error']['type']}"
    )
    assert "not enough experiences" in result["error"]["message"].lower(), (
        f"Expected 'not enough experiences' message, got: {result['error']['message']}"
    )

    # Before fix, this would have returned:
    # {"error": {"type": "internal_error", "message": "Internal server error"}}
