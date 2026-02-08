"""Integration tests for ValueStore with real components."""

from unittest.mock import AsyncMock

import numpy as np
import pytest

from calm.embedding.mock import MockEmbeddingService
from calm.storage.memory import MemoryStore
from calm.values import (
    ClusterInfo,
    ValueStore,
)


@pytest.fixture
async def integration_setup():
    """Set up real components for integration testing."""
    # Real embedding service and vector store
    embedding_service = MockEmbeddingService()
    vector_store = MemoryStore()

    # Create collections
    await vector_store.create_collection("ghap_full", dimension=768)
    await vector_store.create_collection("values", dimension=768)

    # Mock clusterer (SPEC-002-12 not yet implemented)
    clusterer = AsyncMock()

    # Populate some test experiences
    test_experiences = [
        {
            "id": "exp_1",
            "text": "Successfully implemented caching layer for API responses",
            "embedding": await embedding_service.embed(
                "Successfully implemented caching layer for API responses"
            ),
            "confidence_weight": 0.9,
        },
        {
            "id": "exp_2",
            "text": "Reduced database query time by optimizing indexes",
            "embedding": await embedding_service.embed(
                "Reduced database query time by optimizing indexes"
            ),
            "confidence_weight": 0.85,
        },
        {
            "id": "exp_3",
            "text": "Improved performance through better caching strategies",
            "embedding": await embedding_service.embed(
                "Improved performance through better caching strategies"
            ),
            "confidence_weight": 0.95,
        },
    ]

    # Insert experiences into vector store
    for exp in test_experiences:
        await vector_store.upsert(
            collection="ghap_full",
            id=exp["id"],
            vector=exp["embedding"],
            payload={
                "text": exp["text"],
                "confidence_weight": exp["confidence_weight"],
            },
        )

    # Calculate centroid for cluster
    embeddings = [exp["embedding"] for exp in test_experiences]
    centroid = np.mean(embeddings, axis=0)

    # Mock clusterer to return test cluster
    clusterer.cluster_axis.return_value = [
        ClusterInfo(
            cluster_id="full_0",
            axis="full",
            label=0,
            centroid=centroid,
            member_ids=["exp_1", "exp_2", "exp_3"],
            size=3,
            avg_weight=0.9,
        )
    ]
    # Mock count_experiences to return sufficient count (> 20)
    clusterer.count_experiences.return_value = 25

    # Create ValueStore
    value_store = ValueStore(embedding_service, vector_store, clusterer)

    return value_store, vector_store, embedding_service


class TestIntegration:
    """Integration tests with real embedding and storage."""

    async def test_full_workflow(self, integration_setup):
        """Test complete value formation workflow."""
        value_store, vector_store, _ = integration_setup

        # 1. Get clusters
        clusters = await value_store.get_clusters("full")
        assert len(clusters) == 1
        assert clusters[0].cluster_id == "full_0"
        assert clusters[0].size == 3

        # 2. Get cluster members
        members = await value_store.get_cluster_members("full_0")
        assert len(members) == 3
        assert all(hasattr(m, "embedding") for m in members)
        assert all(m.weight > 0 for m in members)

        # 3. Validate a value candidate
        # Use one of the existing experience texts to ensure it's within threshold
        # (MockEmbeddingService produces deterministic but unrelated embeddings)
        candidate_text = "Successfully implemented caching layer for API responses"
        validation = await value_store.validate_value_candidate(
            text=candidate_text, cluster_id="full_0"
        )

        # Should be valid since it's identical to a cluster member
        assert validation.valid is True
        assert validation.similarity is not None
        assert validation.candidate_distance is not None
        assert validation.mean_distance is not None
        assert validation.threshold is not None

        # 4. Store the value
        value = await value_store.store_value(
            text=candidate_text, cluster_id="full_0", axis="full"
        )

        assert value.id.startswith("value_full_0_")
        assert value.text == candidate_text
        assert value.cluster_id == "full_0"
        assert value.cluster_size == 3

        # 5. Verify it was stored in vector store
        stored = await vector_store.get(collection="values", id=value.id)
        assert stored is not None
        assert stored.payload["text"] == candidate_text

        # 6. List values
        values = await value_store.list_values(axis="full")
        assert len(values) == 1
        assert values[0].text == candidate_text

    async def test_invalid_value_rejected(self, integration_setup):
        """Test that distant values are rejected by validation threshold."""
        value_store, _, _ = integration_setup

        # Use text with a different hash to produce a distant embedding
        # MockEmbeddingService generates unrelated embeddings for different texts
        unrelated_text = "Completely different text with different hash"

        validation = await value_store.validate_value_candidate(
            text=unrelated_text, cluster_id="full_0"
        )

        # Should be invalid due to distance from centroid
        assert validation.valid is False
        assert "too far from centroid" in validation.reason
        assert validation.candidate_distance is not None
        assert validation.threshold is not None
        # Verify candidate distance exceeds threshold
        assert validation.candidate_distance > validation.threshold

        # Verify storing fails
        with pytest.raises(ValueError, match="Value failed validation"):
            await value_store.store_value(
                text=unrelated_text, cluster_id="full_0", axis="full"
            )

    async def test_multiple_values_per_cluster(self, integration_setup):
        """Test storing multiple values for the same cluster."""
        value_store, _, _ = integration_setup

        # Use existing experience texts to ensure validation passes
        # Store first value
        value1 = await value_store.store_value(
            text="Successfully implemented caching layer for API responses",
            cluster_id="full_0",
            axis="full",
        )

        # Store second value (different text, also from cluster)
        value2 = await value_store.store_value(
            text="Reduced database query time by optimizing indexes",
            cluster_id="full_0",
            axis="full",
        )

        # List all values
        values = await value_store.list_values(axis="full")
        assert len(values) == 2

        # Should be sorted by created_at (newest first)
        assert values[0].id == value2.id  # Most recent
        assert values[1].id == value1.id

    async def test_real_embedding_consistency(self, integration_setup):
        """Test that real embeddings produce consistent results."""
        value_store, _, embedding_service = integration_setup

        # Validate twice with same text
        text = "Performance optimization"

        result1 = await value_store.validate_value_candidate(
            text=text, cluster_id="full_0"
        )
        result2 = await value_store.validate_value_candidate(
            text=text, cluster_id="full_0"
        )

        # Results should be identical (deterministic embeddings)
        assert result1.valid == result2.valid
        assert result1.candidate_distance == result2.candidate_distance
        assert result1.similarity == result2.similarity
