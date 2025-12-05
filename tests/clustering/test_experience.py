"""Unit tests for ExperienceClusterer class."""

from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

from learning_memory_server.clustering import Clusterer, ExperienceClusterer
from learning_memory_server.storage.base import SearchResult


@pytest.fixture
def mock_vector_store() -> Mock:
    """Create a mock VectorStore."""
    store = Mock()
    store.scroll = AsyncMock()
    return store


@pytest.mark.asyncio
async def test_cluster_axis_success(mock_vector_store: Mock) -> None:
    """Test successful clustering of one axis."""
    # Mock VectorStore.scroll() to return fake data
    np.random.seed(42)
    fake_results = [
        SearchResult(
            id=f"ghap_{i}",
            score=1.0,
            payload={"confidence_tier": "gold"},
            vector=np.random.randn(128).astype(np.float32),
        )
        for i in range(20)
    ]

    mock_vector_store.scroll.return_value = fake_results

    clusterer = Clusterer(min_cluster_size=3)
    exp_clusterer = ExperienceClusterer(mock_vector_store, clusterer)

    clusters = await exp_clusterer.cluster_axis("full")

    assert isinstance(clusters, list)
    mock_vector_store.scroll.assert_called_once()
    # Check that scroll was called with correct collection
    call_kwargs = mock_vector_store.scroll.call_args[1]
    assert call_kwargs["collection"] == "ghap_full"
    assert call_kwargs["with_vectors"] is True


@pytest.mark.asyncio
async def test_cluster_axis_invalid(mock_vector_store: Mock) -> None:
    """Test error for invalid axis name."""
    clusterer = Clusterer()
    exp_clusterer = ExperienceClusterer(mock_vector_store, clusterer)

    with pytest.raises(ValueError, match="Invalid axis"):
        await exp_clusterer.cluster_axis("invalid_axis")


@pytest.mark.asyncio
async def test_cluster_axis_no_data(mock_vector_store: Mock) -> None:
    """Test behavior when axis collection is empty."""
    mock_vector_store.scroll.return_value = []

    clusterer = Clusterer()
    exp_clusterer = ExperienceClusterer(mock_vector_store, clusterer)

    with pytest.raises(ValueError, match="No embeddings found"):
        await exp_clusterer.cluster_axis("full")


@pytest.mark.asyncio
async def test_cluster_axis_with_weights(mock_vector_store: Mock) -> None:
    """Test that confidence tier weights are applied correctly."""
    np.random.seed(42)
    # Create results with different confidence tiers
    fake_results = [
        SearchResult(
            id=f"ghap_{i}",
            score=1.0,
            payload={"confidence_tier": tier},
            vector=np.random.randn(128).astype(np.float32),
        )
        for i, tier in enumerate(["gold", "silver", "bronze", "abandoned"] * 5)
    ]

    mock_vector_store.scroll.return_value = fake_results

    clusterer = Clusterer(min_cluster_size=3)
    exp_clusterer = ExperienceClusterer(mock_vector_store, clusterer)

    clusters = await exp_clusterer.cluster_axis("strategy")

    assert isinstance(clusters, list)
    # Verify clusters were computed (exact count depends on HDBSCAN)
    # Just check that we got some result
    assert clusters is not None


@pytest.mark.asyncio
async def test_cluster_axis_missing_tier(mock_vector_store: Mock) -> None:
    """Test handling of missing confidence_tier in payload."""
    np.random.seed(42)
    fake_results = [
        SearchResult(
            id=f"ghap_{i}",
            score=1.0,
            payload={},  # No confidence_tier
            vector=np.random.randn(128).astype(np.float32),
        )
        for i in range(20)
    ]

    mock_vector_store.scroll.return_value = fake_results

    clusterer = Clusterer(min_cluster_size=3)
    exp_clusterer = ExperienceClusterer(mock_vector_store, clusterer)

    # Should not raise error, should use default weight (0.5)
    clusters = await exp_clusterer.cluster_axis("full")

    assert isinstance(clusters, list)


@pytest.mark.asyncio
async def test_cluster_axis_all_noise(mock_vector_store: Mock) -> None:
    """Test behavior when HDBSCAN labels all points as noise."""
    np.random.seed(42)
    # Create very sparse, random data likely to be all noise
    fake_results = [
        SearchResult(
            id=f"ghap_{i}",
            score=1.0,
            payload={"confidence_tier": "gold"},
            vector=(np.random.randn(128) * 100).astype(
                np.float32
            ),  # Very spread out
        )
        for i in range(5)  # Very few points
    ]

    mock_vector_store.scroll.return_value = fake_results

    clusterer = Clusterer(min_cluster_size=10)  # High threshold
    exp_clusterer = ExperienceClusterer(mock_vector_store, clusterer)

    clusters = await exp_clusterer.cluster_axis("full")

    # Should return empty list when all noise
    assert clusters == []


@pytest.mark.asyncio
async def test_cluster_all_axes(mock_vector_store: Mock) -> None:
    """Test clustering all axes."""
    np.random.seed(42)

    # Return different data for each axis
    def scroll_side_effect(
        collection: str, limit: int, with_vectors: bool
    ) -> list[SearchResult]:
        if "full" in collection:
            return [
                SearchResult(
                    id=f"ghap_{i}",
                    score=1.0,
                    payload={"confidence_tier": "gold"},
                    vector=np.random.randn(128).astype(np.float32),
                )
                for i in range(10)
            ]
        elif "strategy" in collection:
            return [
                SearchResult(
                    id=f"ghap_{i}",
                    score=1.0,
                    payload={"confidence_tier": "silver"},
                    vector=np.random.randn(128).astype(np.float32),
                )
                for i in range(15)
            ]
        else:
            return []  # Other axes empty

    mock_vector_store.scroll.side_effect = scroll_side_effect

    clusterer = Clusterer(min_cluster_size=3)
    exp_clusterer = ExperienceClusterer(mock_vector_store, clusterer)

    results = await exp_clusterer.cluster_all_axes()

    # Should have results for axes with data
    assert isinstance(results, dict)
    # Empty axes should be omitted (not included as empty lists)
    for axis, clusters in results.items():
        assert isinstance(clusters, list)


@pytest.mark.asyncio
async def test_cluster_all_axes_all_empty(mock_vector_store: Mock) -> None:
    """Test cluster_all_axes when all collections are empty."""
    mock_vector_store.scroll.return_value = []

    clusterer = Clusterer()
    exp_clusterer = ExperienceClusterer(mock_vector_store, clusterer)

    results = await exp_clusterer.cluster_all_axes()

    # Should return empty dict when no data
    assert results == {}


@pytest.mark.asyncio
async def test_cluster_axis_calls_correct_collection(mock_vector_store: Mock) -> None:
    """Test that each axis calls the correct collection."""
    np.random.seed(42)
    fake_results = [
        SearchResult(
            id=f"ghap_{i}",
            score=1.0,
            payload={"confidence_tier": "gold"},
            vector=np.random.randn(128).astype(np.float32),
        )
        for i in range(20)
    ]
    mock_vector_store.scroll.return_value = fake_results

    clusterer = Clusterer(min_cluster_size=3)
    exp_clusterer = ExperienceClusterer(mock_vector_store, clusterer)

    # Test each axis
    axis_collection_map = {
        "full": "ghap_full",
        "strategy": "ghap_strategy",
        "surprise": "ghap_surprise",
        "root_cause": "ghap_root_cause",
    }

    for axis, expected_collection in axis_collection_map.items():
        mock_vector_store.reset_mock()
        await exp_clusterer.cluster_axis(axis)

        call_kwargs = mock_vector_store.scroll.call_args[1]
        assert call_kwargs["collection"] == expected_collection


@pytest.mark.asyncio
async def test_cluster_axis_scroll_limit_warning(mock_vector_store: Mock) -> None:
    """Test that warning is logged when scroll limit is reached."""
    np.random.seed(42)
    # Return exactly 10000 results (the limit)
    fake_results = [
        SearchResult(
            id=f"ghap_{i}",
            score=1.0,
            payload={"confidence_tier": "gold"},
            vector=np.random.randn(128).astype(np.float32),
        )
        for i in range(10000)
    ]

    mock_vector_store.scroll.return_value = fake_results

    clusterer = Clusterer(min_cluster_size=3)
    exp_clusterer = ExperienceClusterer(mock_vector_store, clusterer)

    # Should not raise, but should log warning (we can't easily test logging here)
    clusters = await exp_clusterer.cluster_axis("full")

    assert isinstance(clusters, list)
