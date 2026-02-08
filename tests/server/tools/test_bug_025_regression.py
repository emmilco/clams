"""Regression test for BUG-025: MemoryStore should support range filter operators."""

import numpy as np
import pytest

from calm.storage.memory import MemoryStore


@pytest.fixture
async def populated_store() -> MemoryStore:
    """Create an MemoryStore with test data."""
    store = MemoryStore()
    await store.create_collection("test", dimension=4)

    # Insert entries with various timestamps
    for i in range(5):
        vector = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        await store.upsert(
            collection="test",
            id=f"entry-{i}",
            vector=vector,
            payload={"timestamp": 1000 + i * 100, "category": "A" if i % 2 == 0 else "B"},
        )

    return store


@pytest.mark.asyncio
async def test_gte_filter(populated_store: MemoryStore) -> None:
    """Verify $gte filter returns entries with values >= threshold.

    BUG-025: Previously, _apply_filters did strict equality, so
    {"timestamp": {"$gte": 1200}} would never match anything.
    """
    results = await populated_store.scroll(
        collection="test",
        filters={"timestamp": {"$gte": 1200}},
    )

    # Should match entries with timestamp >= 1200 (1200, 1300, 1400)
    assert len(results) == 3
    timestamps = {r.payload["timestamp"] for r in results}
    assert timestamps == {1200, 1300, 1400}


@pytest.mark.asyncio
async def test_lte_filter(populated_store: MemoryStore) -> None:
    """Verify $lte filter returns entries with values <= threshold."""
    results = await populated_store.scroll(
        collection="test",
        filters={"timestamp": {"$lte": 1100}},
    )

    # Should match entries with timestamp <= 1100 (1000, 1100)
    assert len(results) == 2
    timestamps = {r.payload["timestamp"] for r in results}
    assert timestamps == {1000, 1100}


@pytest.mark.asyncio
async def test_gt_filter(populated_store: MemoryStore) -> None:
    """Verify $gt filter returns entries with values > threshold."""
    results = await populated_store.scroll(
        collection="test",
        filters={"timestamp": {"$gt": 1200}},
    )

    # Should match entries with timestamp > 1200 (1300, 1400)
    assert len(results) == 2
    timestamps = {r.payload["timestamp"] for r in results}
    assert timestamps == {1300, 1400}


@pytest.mark.asyncio
async def test_lt_filter(populated_store: MemoryStore) -> None:
    """Verify $lt filter returns entries with values < threshold."""
    results = await populated_store.scroll(
        collection="test",
        filters={"timestamp": {"$lt": 1200}},
    )

    # Should match entries with timestamp < 1200 (1000, 1100)
    assert len(results) == 2
    timestamps = {r.payload["timestamp"] for r in results}
    assert timestamps == {1000, 1100}


@pytest.mark.asyncio
async def test_in_filter(populated_store: MemoryStore) -> None:
    """Verify $in filter returns entries with values in list."""
    results = await populated_store.scroll(
        collection="test",
        filters={"category": {"$in": ["A"]}},
    )

    # Should match entries with category "A" (indices 0, 2, 4)
    assert len(results) == 3
    for r in results:
        assert r.payload["category"] == "A"


@pytest.mark.asyncio
async def test_combined_range_filters(populated_store: MemoryStore) -> None:
    """Verify multiple range operators can be combined."""
    results = await populated_store.scroll(
        collection="test",
        filters={"timestamp": {"$gte": 1100, "$lte": 1300}},
    )

    # Should match entries with 1100 <= timestamp <= 1300
    assert len(results) == 3
    timestamps = {r.payload["timestamp"] for r in results}
    assert timestamps == {1100, 1200, 1300}


@pytest.mark.asyncio
async def test_range_filter_with_equality(populated_store: MemoryStore) -> None:
    """Verify range filter can be combined with equality filter."""
    results = await populated_store.scroll(
        collection="test",
        filters={
            "timestamp": {"$gte": 1100},
            "category": "A",
        },
    )

    # Should match: category="A" AND timestamp >= 1100
    # That's entries 2 (ts=1200, cat=A) and 4 (ts=1400, cat=A)
    assert len(results) == 2
    for r in results:
        assert r.payload["category"] == "A"
        assert r.payload["timestamp"] >= 1100


@pytest.mark.asyncio
async def test_simple_equality_still_works(populated_store: MemoryStore) -> None:
    """Verify simple equality filters still work after adding operator support."""
    results = await populated_store.scroll(
        collection="test",
        filters={"timestamp": 1200},
    )

    assert len(results) == 1
    assert results[0].payload["timestamp"] == 1200
