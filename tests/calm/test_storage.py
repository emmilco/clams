"""Tests for CALM storage modules."""

import numpy as np
import pytest

from calm.storage import MemoryStore, SearchResult, VectorStore


class TestMemoryStore:
    """Test in-memory vector store implementation."""

    @pytest.fixture
    async def store(self) -> MemoryStore:
        """Create a MemoryStore instance for testing."""
        store = MemoryStore()
        await store.create_collection("test", dimension=384)
        return store

    @pytest.mark.asyncio
    async def test_create_collection(self) -> None:
        """Test collection creation."""
        store = MemoryStore()
        await store.create_collection("test", dimension=384)

        info = await store.get_collection_info("test")
        assert info is not None
        assert info.name == "test"
        assert info.dimension == 384
        assert info.vector_count == 0

    @pytest.mark.asyncio
    async def test_create_duplicate_collection_fails(self) -> None:
        """Test that creating duplicate collection raises error."""
        store = MemoryStore()
        await store.create_collection("test", dimension=384)

        with pytest.raises(ValueError, match="already exists"):
            await store.create_collection("test", dimension=384)

    @pytest.mark.asyncio
    async def test_upsert_and_get(self, store: MemoryStore) -> None:
        """Test upserting and retrieving a vector."""
        vector = np.random.randn(384).astype(np.float32)
        payload = {"key": "value", "num": 42}

        await store.upsert(
            collection="test",
            id="vec1",
            vector=vector,
            payload=payload,
        )

        result = await store.get("test", "vec1")
        assert result is not None
        assert result.id == "vec1"
        assert result.payload["key"] == "value"
        assert result.payload["num"] == 42

    @pytest.mark.asyncio
    async def test_search(self, store: MemoryStore) -> None:
        """Test vector similarity search."""
        # Create some vectors
        for i in range(5):
            vector = np.random.randn(384).astype(np.float32)
            await store.upsert(
                collection="test",
                id=f"vec{i}",
                vector=vector,
                payload={"index": i},
            )

        # Search with a query vector
        query = np.random.randn(384).astype(np.float32)
        results = await store.search("test", query, limit=3)

        assert len(results) == 3
        # Results should be sorted by score (descending)
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

    @pytest.mark.asyncio
    async def test_search_with_filter(self, store: MemoryStore) -> None:
        """Test search with filters."""
        # Create vectors with different categories
        for i in range(10):
            vector = np.random.randn(384).astype(np.float32)
            await store.upsert(
                collection="test",
                id=f"vec{i}",
                vector=vector,
                payload={"category": "A" if i < 5 else "B"},
            )

        # Search only category A
        query = np.random.randn(384).astype(np.float32)
        results = await store.search("test", query, limit=10, filters={"category": "A"})

        assert len(results) == 5
        for r in results:
            assert r.payload["category"] == "A"

    @pytest.mark.asyncio
    async def test_delete(self, store: MemoryStore) -> None:
        """Test deleting a vector."""
        vector = np.random.randn(384).astype(np.float32)
        await store.upsert(
            collection="test",
            id="vec1",
            vector=vector,
            payload={"key": "value"},
        )

        # Verify it exists
        result = await store.get("test", "vec1")
        assert result is not None

        # Delete it
        await store.delete("test", "vec1")

        # Verify it's gone
        result = await store.get("test", "vec1")
        assert result is None

    @pytest.mark.asyncio
    async def test_count(self, store: MemoryStore) -> None:
        """Test counting vectors."""
        # Initially empty
        count = await store.count("test")
        assert count == 0

        # Add some vectors
        for i in range(5):
            vector = np.random.randn(384).astype(np.float32)
            await store.upsert(
                collection="test",
                id=f"vec{i}",
                vector=vector,
                payload={"category": "A" if i < 3 else "B"},
            )

        # Total count
        count = await store.count("test")
        assert count == 5

        # Filtered count
        count = await store.count("test", filters={"category": "A"})
        assert count == 3

    @pytest.mark.asyncio
    async def test_scroll(self, store: MemoryStore) -> None:
        """Test scrolling through vectors."""
        # Add vectors
        for i in range(10):
            vector = np.random.randn(384).astype(np.float32)
            await store.upsert(
                collection="test",
                id=f"vec{i}",
                vector=vector,
                payload={"index": i},
            )

        # Scroll with limit
        results = await store.scroll("test", limit=5)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_range_filter(self, store: MemoryStore) -> None:
        """Test range filters ($gte, $lte)."""
        for i in range(10):
            vector = np.random.randn(384).astype(np.float32)
            await store.upsert(
                collection="test",
                id=f"vec{i}",
                vector=vector,
                payload={"value": i},
            )

        # Filter value >= 5
        results = await store.scroll("test", limit=20, filters={"value": {"$gte": 5}})
        assert len(results) == 5
        for r in results:
            assert r.payload["value"] >= 5

        # Filter value < 3
        results = await store.scroll("test", limit=20, filters={"value": {"$lt": 3}})
        assert len(results) == 3
        for r in results:
            assert r.payload["value"] < 3
