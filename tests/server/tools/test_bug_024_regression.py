"""Regression test for BUG-024: InMemoryVectorStore error message should match Searcher expectation."""

import numpy as np
import pytest

from clams.storage.memory import InMemoryVectorStore


@pytest.fixture
def vector_store() -> InMemoryVectorStore:
    """Create an InMemoryVectorStore instance."""
    return InMemoryVectorStore()


@pytest.mark.asyncio
async def test_inmemory_error_message_contains_not_found(
    vector_store: InMemoryVectorStore,
) -> None:
    """Verify InMemoryVectorStore uses 'not found' in error messages.

    BUG-024: Previously, InMemoryVectorStore used 'does not exist' in error
    messages, but Searcher checks for 'not found' to convert to
    CollectionNotFoundError. The mismatch meant the conversion never happened.
    """
    with pytest.raises(ValueError, match="not found"):
        await vector_store.delete_collection("nonexistent")


@pytest.mark.asyncio
async def test_inmemory_search_raises_collection_not_found(
    vector_store: InMemoryVectorStore,
) -> None:
    """Verify search on non-existent collection raises ValueError with 'not found'."""
    query = np.array([0.1] * 768, dtype=np.float32)

    with pytest.raises(ValueError, match="not found"):
        await vector_store.search("nonexistent", query)


@pytest.mark.asyncio
async def test_inmemory_upsert_raises_collection_not_found(
    vector_store: InMemoryVectorStore,
) -> None:
    """Verify upsert to non-existent collection raises ValueError with 'not found'."""
    vector = np.array([0.1] * 768, dtype=np.float32)

    with pytest.raises(ValueError, match="not found"):
        await vector_store.upsert("nonexistent", "id1", vector, {"key": "value"})


@pytest.mark.asyncio
async def test_inmemory_scroll_raises_collection_not_found(
    vector_store: InMemoryVectorStore,
) -> None:
    """Verify scroll on non-existent collection raises ValueError with 'not found'."""
    with pytest.raises(ValueError, match="not found"):
        await vector_store.scroll("nonexistent")


@pytest.mark.asyncio
async def test_inmemory_count_raises_collection_not_found(
    vector_store: InMemoryVectorStore,
) -> None:
    """Verify count on non-existent collection raises ValueError with 'not found'."""
    with pytest.raises(ValueError, match="not found"):
        await vector_store.count("nonexistent")


@pytest.mark.asyncio
async def test_inmemory_get_raises_collection_not_found(
    vector_store: InMemoryVectorStore,
) -> None:
    """Verify get on non-existent collection raises ValueError with 'not found'."""
    with pytest.raises(ValueError, match="not found"):
        await vector_store.get("nonexistent", "id1")


@pytest.mark.asyncio
async def test_inmemory_delete_raises_collection_not_found(
    vector_store: InMemoryVectorStore,
) -> None:
    """Verify delete on non-existent collection raises ValueError with 'not found'."""
    with pytest.raises(ValueError, match="not found"):
        await vector_store.delete("nonexistent", "id1")
