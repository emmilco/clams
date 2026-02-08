"""Regression test for BUG-017: get_clusters returns internal server error.

Tests that get_clusters returns InsufficientDataError (not internal_error)
when GHAP collections don't exist.
"""

import numpy as np
import pytest

from calm.clustering import Clusterer, ExperienceClusterer
from calm.embedding.base import EmbeddingService, Vector
from calm.tools.learning import get_learning_tools
from calm.storage.qdrant import QdrantVectorStore
from calm.values import ValueStore


class MockEmbedder(EmbeddingService):
    """Mock embedding service for testing.

    IMPORTANT: This mock must match the interface of EmbeddingService.
    Interface parity is verified by tests/infrastructure/test_mock_parity.py.
    If you modify this class, run those tests to ensure interface compatibility.
    See BUG-040, BUG-041 for examples of bugs caused by mock/production drift.
    """

    @property
    def dimension(self) -> int:
        return 768

    async def embed(self, text: str) -> Vector:
        return np.array([0.1] * 768, dtype=np.float32)

    async def embed_batch(self, texts: list[str]) -> list[Vector]:
        return [np.array([0.1] * 768, dtype=np.float32) for _ in texts]


@pytest.mark.asyncio
async def test_bug_017_regression_get_clusters_no_collection() -> None:
    """Test that get_clusters returns error status (not internal_error).

    Regression test for BUG-017 where missing GHAP collections caused
    UnexpectedResponse to fall through to generic Exception handler,
    returning "internal_error" instead of a proper error response.
    """
    # Setup: in-memory Qdrant with NO collections created
    vector_store = QdrantVectorStore(url=":memory:")
    embedder = MockEmbedder()
    clusterer = Clusterer()
    experience_clusterer = ExperienceClusterer(
        vector_store=vector_store,
        clusterer=clusterer,
    )

    value_store = ValueStore(
        embedding_service=embedder,
        vector_store=vector_store,
        clusterer=experience_clusterer,
    )

    tools = get_learning_tools(
        vector_store=vector_store,
        semantic_embedder=embedder,
        experience_clusterer=experience_clusterer,
        value_store=value_store,
    )
    get_clusters = tools["get_clusters"]

    # Action: call get_clusters on non-existent collection
    result = await get_clusters(axis="full")

    # Assert: should return error status (not internal_error)
    # When collections don't exist, value_store.get_clusters raises ValueError
    # which is caught and returns {"status": "error", "message": ...}
    assert "status" in result, "Expected status response"
    assert result["status"] == "error", (
        f"Expected error status, got {result['status']}"
    )
    assert "not enough experiences" in result["message"].lower(), (
        f"Expected 'not enough experiences' message, got: {result['message']}"
    )

    # Before fix, this would have returned:
    # {"error": {"type": "internal_error", "message": "Internal server error"}}
