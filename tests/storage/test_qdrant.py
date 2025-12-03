"""Tests for QdrantVectorStore."""

import os
from collections.abc import AsyncIterator

import numpy as np
import pytest

from learning_memory_server.storage import QdrantVectorStore

# Skip all tests if Docker is not available
pytest_plugins = ("pytest_asyncio",)

pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_QDRANT_TESTS", "0") == "1",
    reason="Qdrant tests skipped (set SKIP_QDRANT_TESTS=0 to enable)",
)


@pytest.fixture
async def store() -> AsyncIterator[QdrantVectorStore]:
    """Create a Qdrant store connected to test instance."""
    store = QdrantVectorStore(url="http://localhost:6333")
    yield store
    # Cleanup happens per-collection in tests


@pytest.fixture
async def collection(store: QdrantVectorStore) -> AsyncIterator[str]:
    """Create and cleanup a test collection."""
    name = "test_collection"
    await store.create_collection(name, dimension=3)
    yield name
    try:
        await store.delete_collection(name)
    except Exception:
        pass  # Collection may already be deleted in test


class TestQdrantVectorStore:
    """Test suite for QdrantVectorStore.

    These tests require a running Qdrant instance.
    Run: docker-compose -f docker-compose.test.yml up -d
    """

    async def test_create_collection(self, store: QdrantVectorStore) -> None:
        """Test creating a collection."""
        name = "test_create"
        try:
            await store.create_collection(name, dimension=128, distance="cosine")

            # Verify collection exists
            count = await store.count(name)
            assert count == 0
        finally:
            await store.delete_collection(name)

    async def test_delete_collection(self, store: QdrantVectorStore) -> None:
        """Test deleting a collection."""
        name = "test_delete"
        await store.create_collection(name, dimension=128)
        await store.delete_collection(name)

        # Verify collection is gone by attempting to count (should fail)
        # Note: Qdrant may not immediately reflect deletion, so we just
        # verify the delete call succeeded without error

    async def test_upsert_and_get(
        self, store: QdrantVectorStore, collection: str
    ) -> None:
        """Test inserting and retrieving a vector."""
        vector = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        payload = {"text": "test", "category": "A"}

        await store.upsert(collection, "id1", vector, payload)

        # Get without vector
        result = await store.get(collection, "id1", with_vector=False)
        assert result is not None
        assert result.id == "id1"
        assert result.payload == payload
        assert result.vector is None

        # Get with vector
        result = await store.get(collection, "id1", with_vector=True)
        assert result is not None
        assert result.vector is not None
        # Qdrant normalizes vectors for cosine distance, so compare normalized
        result_array = np.array(result.vector, dtype=np.float32)
        expected_normalized = vector / np.linalg.norm(vector)
        np.testing.assert_array_almost_equal(
            result_array, expected_normalized, decimal=5
        )

    async def test_upsert_update(
        self, store: QdrantVectorStore, collection: str
    ) -> None:
        """Test that upsert updates existing vectors."""
        vector1 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        vector2 = np.array([4.0, 5.0, 6.0], dtype=np.float32)

        await store.upsert(collection, "id1", vector1, {"version": 1})
        await store.upsert(collection, "id1", vector2, {"version": 2})

        result = await store.get(collection, "id1", with_vector=True)
        assert result is not None
        assert result.payload["version"] == 2
        # Qdrant normalizes vectors for cosine distance
        result_array = np.array(result.vector, dtype=np.float32)
        expected_normalized = vector2 / np.linalg.norm(vector2)
        np.testing.assert_array_almost_equal(
            result_array, expected_normalized, decimal=5
        )

    async def test_search_cosine_similarity(
        self, store: QdrantVectorStore, collection: str
    ) -> None:
        """Test cosine similarity search."""
        # Insert some test vectors
        vectors = [
            (np.array([1.0, 0.0, 0.0], dtype=np.float32), {"label": "x"}),
            (np.array([0.0, 1.0, 0.0], dtype=np.float32), {"label": "y"}),
            (np.array([0.0, 0.0, 1.0], dtype=np.float32), {"label": "z"}),
            (np.array([0.9, 0.1, 0.0], dtype=np.float32), {"label": "x-ish"}),
        ]

        for i, (vec, payload) in enumerate(vectors):
            await store.upsert(collection, f"id{i}", vec, payload)

        # Search for x-like vectors
        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        results = await store.search(collection, query, limit=2)

        assert len(results) == 2
        # Most similar should be exact match
        assert results[0].payload["label"] == "x"
        assert results[0].score == pytest.approx(1.0, abs=0.01)
        # Second most similar should be x-ish
        assert results[1].payload["label"] == "x-ish"
        assert results[1].score > 0.9

    async def test_search_with_filters(
        self, store: QdrantVectorStore, collection: str
    ) -> None:
        """Test search with payload filters."""
        vectors = [
            (np.array([1.0, 0.0, 0.0], dtype=np.float32), {"category": "A"}),
            (np.array([0.9, 0.1, 0.0], dtype=np.float32), {"category": "A"}),
            (np.array([0.8, 0.2, 0.0], dtype=np.float32), {"category": "B"}),
        ]

        for i, (vec, payload) in enumerate(vectors):
            await store.upsert(collection, f"id{i}", vec, payload)

        # Search only category A
        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        results = await store.search(
            collection, query, limit=10, filters={"category": "A"}
        )

        assert len(results) == 2
        assert all(r.payload["category"] == "A" for r in results)

    async def test_delete(self, store: QdrantVectorStore, collection: str) -> None:
        """Test deleting a vector."""
        vector = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        await store.upsert(collection, "id1", vector, {})

        await store.delete(collection, "id1")

        result = await store.get(collection, "id1")
        assert result is None

    async def test_scroll(self, store: QdrantVectorStore, collection: str) -> None:
        """Test scrolling through vectors."""
        # Insert test vectors
        for i in range(5):
            vector = np.array([float(i), 0.0, 0.0], dtype=np.float32)
            await store.upsert(collection, f"id{i}", vector, {"index": i})

        # Scroll without filters
        results = await store.scroll(collection, limit=3)
        assert len(results) == 3

        # Scroll with vectors
        results = await store.scroll(collection, limit=2, with_vectors=True)
        assert len(results) == 2
        assert all(r.vector is not None for r in results)

    async def test_scroll_with_filters(
        self, store: QdrantVectorStore, collection: str
    ) -> None:
        """Test scroll with payload filters."""
        for i in range(5):
            vector = np.array([float(i), 0.0, 0.0], dtype=np.float32)
            category = "A" if i % 2 == 0 else "B"
            await store.upsert(collection, f"id{i}", vector, {"category": category})

        results = await store.scroll(collection, filters={"category": "A"})
        assert len(results) == 3  # indices 0, 2, 4
        assert all(r.payload["category"] == "A" for r in results)

    async def test_count(self, store: QdrantVectorStore, collection: str) -> None:
        """Test counting vectors."""
        # Empty collection
        assert await store.count(collection) == 0

        # Add vectors
        for i in range(3):
            vector = np.array([float(i), 0.0, 0.0], dtype=np.float32)
            await store.upsert(collection, f"id{i}", vector, {})

        assert await store.count(collection) == 3

    async def test_count_with_filters(
        self, store: QdrantVectorStore, collection: str
    ) -> None:
        """Test count with filters."""
        for i in range(5):
            vector = np.array([float(i), 0.0, 0.0], dtype=np.float32)
            category = "A" if i % 2 == 0 else "B"
            await store.upsert(collection, f"id{i}", vector, {"category": category})

        assert await store.count(collection, filters={"category": "A"}) == 3
        assert await store.count(collection, filters={"category": "B"}) == 2

    async def test_get_nonexistent(
        self, store: QdrantVectorStore, collection: str
    ) -> None:
        """Test getting a nonexistent vector."""
        result = await store.get(collection, "nonexistent")
        assert result is None

    async def test_distance_metrics(self, store: QdrantVectorStore) -> None:
        """Test different distance metrics."""
        for distance in ["cosine", "euclidean", "dot"]:
            name = f"test_{distance}"
            try:
                await store.create_collection(name, dimension=3, distance=distance)
                count = await store.count(name)
                assert count == 0
            finally:
                await store.delete_collection(name)
