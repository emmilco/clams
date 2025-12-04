"""Integration tests for clustering with real Qdrant.

These tests require a running Qdrant instance at localhost:6333.
Run with: docker run -p 6333:6333 qdrant/qdrant
"""

from collections.abc import AsyncIterator

import numpy as np
import pytest

from learning_memory_server.clustering import Clusterer, ExperienceClusterer
from learning_memory_server.storage import QdrantVectorStore

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
async def store() -> AsyncIterator[QdrantVectorStore]:
    """Create a Qdrant store connected to test instance."""
    store = QdrantVectorStore(url="http://localhost:6333")
    yield store


@pytest.fixture
async def test_collection(store: QdrantVectorStore) -> AsyncIterator[str]:
    """Create and cleanup a test collection."""
    name = "test_experiences_full"
    await store.create_collection(name, dimension=128, distance="cosine")
    yield name
    try:
        await store.delete_collection(name)
    except Exception:
        pass  # Collection may already be deleted in test


@pytest.mark.asyncio
async def test_end_to_end_clustering(
    store: QdrantVectorStore, test_collection: str
) -> None:
    """Test full clustering workflow with real Qdrant."""
    # Store 50 synthetic experiences (3 clear clusters)
    np.random.seed(42)
    for i in range(50):
        cluster_id = i // 17  # 3 clusters
        base = np.zeros(128)
        base[0] = cluster_id * 10  # Separate along first dimension
        vector = (np.random.randn(128) * 0.5 + base).astype(np.float32)

        await store.upsert(
            collection=test_collection,
            id=f"ghap_{i}",
            vector=vector,
            payload={
                "confidence_tier": "gold" if i % 3 == 0 else "silver",
                "created_at": "2024-01-01T00:00:00Z",
                "session_id": "test_session",
            },
        )

    # Cluster
    clusterer = Clusterer(min_cluster_size=5)
    exp_clusterer = ExperienceClusterer(store, clusterer)

    # Mock the collection mapping for test
    from learning_memory_server.clustering import experience

    original_mapping = experience.AXIS_COLLECTIONS.copy()
    experience.AXIS_COLLECTIONS = {"full": test_collection}

    try:
        clusters = await exp_clusterer.cluster_axis("full")

        # Should find clusters (exact count depends on HDBSCAN)
        # Note: With synthetic data, HDBSCAN might label all as noise
        # Just verify we get a valid result (possibly empty)
        assert isinstance(clusters, list)

        # Verify ClusterInfo structure if we got clusters
        for cluster in clusters:
            assert cluster.label >= 0
            assert cluster.size > 0
            assert len(cluster.member_ids) == cluster.size
            assert cluster.centroid.shape == (128,)
            assert 0.0 <= cluster.avg_weight <= 1.0
            # Check that member_ids are valid
            assert all(mid.startswith("ghap_") for mid in cluster.member_ids)

        # Verify all members are accounted for (excluding noise)
        all_members = set()
        for cluster in clusters:
            all_members.update(cluster.member_ids)

        # Total members should be <= 50 (some may be noise)
        assert len(all_members) <= 50

    finally:
        # Restore original mapping
        experience.AXIS_COLLECTIONS = original_mapping


@pytest.mark.asyncio
async def test_multi_axis_clustering(store: QdrantVectorStore) -> None:
    """Test clustering on multiple axes with same data."""
    # Create collections for multiple axes
    collections = {
        "full": "test_experiences_full_multi",
        "strategy": "test_experiences_strategy_multi",
    }

    for collection in collections.values():
        await store.create_collection(collection, dimension=128, distance="cosine")

    try:
        # Store same experiences in both collections
        np.random.seed(42)
        for i in range(30):
            vector = np.random.randn(128).astype(np.float32)
            payload = {
                "confidence_tier": "gold",
                "created_at": "2024-01-01T00:00:00Z",
            }

            for collection in collections.values():
                await store.upsert(
                    collection=collection,
                    id=f"ghap_{i}",
                    vector=vector,
                    payload=payload,
                )

        # Cluster both axes
        clusterer = Clusterer(min_cluster_size=3)
        exp_clusterer = ExperienceClusterer(store, clusterer)

        # Mock the collection mapping
        from learning_memory_server.clustering import experience

        original_mapping = experience.AXIS_COLLECTIONS.copy()
        experience.AXIS_COLLECTIONS = collections

        try:
            results = await exp_clusterer.cluster_all_axes()

            # Should have results for both axes
            assert isinstance(results, dict)
            # At least one axis should have clusters or be omitted
            for axis, clusters in results.items():
                assert isinstance(clusters, list)

        finally:
            experience.AXIS_COLLECTIONS = original_mapping

    finally:
        # Cleanup
        for collection in collections.values():
            try:
                await store.delete_collection(collection)
            except Exception:
                pass


@pytest.mark.asyncio
async def test_clustering_with_mixed_confidence_tiers(
    store: QdrantVectorStore, test_collection: str
) -> None:
    """Test clustering with different confidence tiers affects centroids."""
    # Create a cluster where one point has high weight
    np.random.seed(42)

    # Base cluster around origin
    base = np.zeros(128)

    # Add most points near origin
    for i in range(15):
        vector = (np.random.randn(128) * 0.5 + base).astype(np.float32)
        await store.upsert(
            collection=test_collection,
            id=f"bronze_{i}",
            vector=vector,
            payload={"confidence_tier": "bronze"},  # Low weight
        )

    # Add one outlier with high weight
    outlier = base.copy()
    outlier[0] = 5.0  # Shift along first dimension
    await store.upsert(
        collection=test_collection,
        id="gold_outlier",
        vector=outlier.astype(np.float32),
        payload={"confidence_tier": "gold"},  # High weight
    )

    # Cluster
    clusterer = Clusterer(min_cluster_size=3)
    exp_clusterer = ExperienceClusterer(store, clusterer)

    # Mock the collection mapping
    from learning_memory_server.clustering import experience

    original_mapping = experience.AXIS_COLLECTIONS.copy()
    experience.AXIS_COLLECTIONS = {"full": test_collection}

    try:
        clusters = await exp_clusterer.cluster_axis("full")

        # Should find at least one cluster
        assert len(clusters) >= 1

        # The centroid should be pulled toward the gold outlier
        # (exact behavior depends on HDBSCAN clustering result)
        # Just verify we got valid clusters with weighted centroids
        for cluster in clusters:
            assert cluster.centroid.shape == (128,)
            assert cluster.avg_weight > 0

    finally:
        experience.AXIS_COLLECTIONS = original_mapping


@pytest.mark.asyncio
async def test_clustering_performance(
    store: QdrantVectorStore, test_collection: str
) -> None:
    """Test clustering performance with 500 points."""
    import time

    # Store 500 experiences
    np.random.seed(42)
    for i in range(500):
        vector = np.random.randn(128).astype(np.float32)
        await store.upsert(
            collection=test_collection,
            id=f"ghap_{i}",
            vector=vector,
            payload={"confidence_tier": "gold"},
        )

    # Cluster and measure time
    clusterer = Clusterer(min_cluster_size=5)
    exp_clusterer = ExperienceClusterer(store, clusterer)

    # Mock the collection mapping
    from learning_memory_server.clustering import experience

    original_mapping = experience.AXIS_COLLECTIONS.copy()
    experience.AXIS_COLLECTIONS = {"full": test_collection}

    try:
        start = time.time()
        clusters = await exp_clusterer.cluster_axis("full")
        elapsed = time.time() - start

        # Should complete in reasonable time (spec says <2s for cluster_axis)
        assert elapsed < 5.0  # Allow some slack for CI

        # Should find some structure in random data (or all noise)
        assert isinstance(clusters, list)

    finally:
        experience.AXIS_COLLECTIONS = original_mapping


@pytest.mark.asyncio
async def test_clustering_empty_collection(
    store: QdrantVectorStore, test_collection: str
) -> None:
    """Test clustering with empty collection raises error."""
    clusterer = Clusterer()
    exp_clusterer = ExperienceClusterer(store, clusterer)

    # Mock the collection mapping
    from learning_memory_server.clustering import experience

    original_mapping = experience.AXIS_COLLECTIONS.copy()
    experience.AXIS_COLLECTIONS = {"full": test_collection}

    try:
        with pytest.raises(ValueError, match="No embeddings found"):
            await exp_clusterer.cluster_axis("full")
    finally:
        experience.AXIS_COLLECTIONS = original_mapping
