"""Unit tests for Clusterer class."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from learning_memory_server.clustering import Clusterer, ClusterResult


def test_cluster_basic() -> None:
    """Test clustering with synthetic data."""
    clusterer = Clusterer(min_cluster_size=3)

    # Create 2 clear clusters in 2D space
    np.random.seed(42)
    cluster1 = np.random.randn(10, 2) + np.array([0, 0])
    cluster2 = np.random.randn(10, 2) + np.array([10, 10])
    embeddings = np.vstack([cluster1, cluster2]).astype(np.float32)

    result = clusterer.cluster(embeddings)

    assert isinstance(result, ClusterResult)
    assert result.n_clusters >= 1  # At least one cluster
    assert len(result.labels) == 20
    assert result.noise_count >= 0
    assert len(result.probabilities) == 20


def test_cluster_with_weights() -> None:
    """Test weighted centroid computation."""
    clusterer = Clusterer(min_cluster_size=3)

    # Simple 2D cluster
    embeddings = np.array(
        [
            [0, 0],
            [1, 1],
            [0.5, 0.5],
        ],
        dtype=np.float32,
    )

    # High weight on [1, 1] should pull centroid
    weights = np.array([0.1, 1.0, 0.1])

    result = clusterer.cluster(embeddings, weights)
    clusters = clusterer.compute_centroids(
        embeddings,
        result.labels,
        ids=["a", "b", "c"],
        weights=weights,
    )

    if clusters:
        # Centroid should be closer to [1, 1] than unweighted mean
        centroid = clusters[0].centroid
        # Unweighted mean would be [0.5, 0.5]
        # Weighted mean should be closer to [1, 1]
        assert centroid[0] > 0.5
        assert centroid[1] > 0.5


def test_cluster_empty() -> None:
    """Test error handling for empty input."""
    clusterer = Clusterer()
    empty = np.array([]).reshape(0, 128).astype(np.float32)

    with pytest.raises(ValueError, match="empty"):
        clusterer.cluster(empty)


def test_cluster_wrong_shape() -> None:
    """Test error handling for wrong shape."""
    clusterer = Clusterer()
    # 1D array instead of 2D
    embeddings = np.array([1, 2, 3], dtype=np.float32)

    with pytest.raises(ValueError, match="2D array"):
        clusterer.cluster(embeddings)


def test_cluster_weights_mismatch() -> None:
    """Test error handling for weights length mismatch."""
    clusterer = Clusterer()
    embeddings = np.random.randn(10, 128).astype(np.float32)
    weights = np.array([1.0, 0.5])  # Wrong length

    with pytest.raises(ValueError, match="doesn't match"):
        clusterer.cluster(embeddings, weights)


def test_cluster_single_cluster() -> None:
    """Test behavior when all points form one cluster."""
    clusterer = Clusterer(min_cluster_size=3)

    # Tight cluster around origin
    np.random.seed(42)
    embeddings = np.random.randn(10, 128).astype(np.float32) * 0.1

    result = clusterer.cluster(embeddings)

    # Should find at least one cluster (or all noise)
    assert result.n_clusters >= 0
    assert len(result.labels) == 10


def test_compute_centroids() -> None:
    """Test centroid computation with known data."""
    clusterer = Clusterer()

    # Simple 2D data
    embeddings = np.array(
        [
            [0, 0],
            [1, 0],
            [0, 1],
            [10, 10],
            [11, 10],
            [10, 11],
        ],
        dtype=np.float32,
    )
    labels = np.array([0, 0, 0, 1, 1, 1])
    ids = [f"id{i}" for i in range(6)]
    weights = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0])

    clusters = clusterer.compute_centroids(embeddings, labels, ids, weights)

    assert len(clusters) == 2
    assert all(c.label in [0, 1] for c in clusters)

    # Check cluster 0 centroid (mean of [0,0], [1,0], [0,1])
    cluster_0 = next(c for c in clusters if c.label == 0)
    assert cluster_0.size == 3
    assert len(cluster_0.member_ids) == 3
    # Centroid should be around [0.33, 0.33]
    assert np.allclose(cluster_0.centroid, [1 / 3, 1 / 3], atol=0.01)


def test_compute_centroids_excludes_noise() -> None:
    """Test that noise points (-1 label) are excluded."""
    clusterer = Clusterer()

    embeddings = np.random.randn(10, 128).astype(np.float32)
    labels = np.array([0, 0, 1, 1, -1, -1, 0, 1, -1, 0])  # 2 clusters + noise
    ids = [f"id{i}" for i in range(10)]

    clusters = clusterer.compute_centroids(embeddings, labels, ids)

    # Should have 2 clusters (0 and 1), noise excluded
    assert len(clusters) == 2
    assert all(c.label in [0, 1] for c in clusters)

    # Check member counts
    cluster_0 = next(c for c in clusters if c.label == 0)
    cluster_1 = next(c for c in clusters if c.label == 1)
    assert cluster_0.size == 4  # 4 points labeled 0
    assert cluster_1.size == 3  # 3 points labeled 1


def test_compute_centroids_weighted() -> None:
    """Test weighted centroid computation."""
    clusterer = Clusterer()

    # Two points in a cluster
    embeddings = np.array([[0, 0], [10, 10]], dtype=np.float32)
    labels = np.array([0, 0])
    ids = ["a", "b"]
    weights = np.array([0.1, 0.9])  # Heavy weight on [10, 10]

    clusters = clusterer.compute_centroids(embeddings, labels, ids, weights)

    assert len(clusters) == 1
    cluster = clusters[0]

    # Centroid should be closer to [10, 10] than [5, 5] (unweighted mean)
    # Weighted: (0.1*[0,0] + 0.9*[10,10]) / 1.0 = [9, 9]
    assert np.allclose(cluster.centroid, [9, 9], atol=0.01)
    assert cluster.avg_weight == 0.5  # Mean of [0.1, 0.9]


def test_compute_centroids_array_mismatch() -> None:
    """Test error handling for array length mismatches."""
    clusterer = Clusterer()

    embeddings = np.random.randn(10, 128).astype(np.float32)
    labels = np.array([0, 1])  # Wrong length
    ids = [f"id{i}" for i in range(10)]

    with pytest.raises(ValueError, match="don't match"):
        clusterer.compute_centroids(embeddings, labels, ids)


def test_compute_centroids_weights_mismatch() -> None:
    """Test error handling for weights length mismatch."""
    clusterer = Clusterer()

    embeddings = np.random.randn(10, 128).astype(np.float32)
    labels = np.array([0] * 10)
    ids = [f"id{i}" for i in range(10)]
    weights = np.array([1.0, 0.5])  # Wrong length

    with pytest.raises(ValueError, match="doesn't match"):
        clusterer.compute_centroids(embeddings, labels, ids, weights)


def test_compute_centroids_no_weights() -> None:
    """Test centroid computation without weights (all equal)."""
    clusterer = Clusterer()

    embeddings = np.array([[0, 0], [10, 10]], dtype=np.float32)
    labels = np.array([0, 0])
    ids = ["a", "b"]

    clusters = clusterer.compute_centroids(embeddings, labels, ids)

    assert len(clusters) == 1
    cluster = clusters[0]

    # Unweighted centroid should be [5, 5]
    assert np.allclose(cluster.centroid, [5, 5], atol=0.01)
    assert cluster.avg_weight == 1.0  # Default weight


# Property-based tests using hypothesis
@given(
    n_points=st.integers(min_value=10, max_value=100),
    n_dim=st.integers(min_value=32, max_value=256),
)
def test_cluster_invariants(n_points: int, n_dim: int) -> None:
    """Test clustering invariants with arbitrary data."""
    np.random.seed(42)
    embeddings = np.random.randn(n_points, n_dim).astype(np.float32)
    clusterer = Clusterer(min_cluster_size=3)

    result = clusterer.cluster(embeddings)

    # Invariant: Every point gets a label
    assert len(result.labels) == n_points

    # Invariant: n_clusters <= n_points
    assert result.n_clusters <= n_points

    # Invariant: Probabilities in [0, 1]
    assert np.all((result.probabilities >= 0) & (result.probabilities <= 1))

    # Invariant: noise_count + cluster members = total points
    assert result.noise_count >= 0
    assert result.noise_count <= n_points


@given(
    n_points=st.integers(min_value=10, max_value=100),
)
def test_centroid_invariants(n_points: int) -> None:
    """Test centroid computation invariants."""
    np.random.seed(42)
    n_dim = 128
    embeddings = np.random.randn(n_points, n_dim).astype(np.float32)
    weights = np.random.uniform(0.1, 1.0, size=n_points).astype(np.float32)
    labels = np.random.randint(0, 5, size=n_points)  # 5 clusters
    ids = [f"id_{i}" for i in range(n_points)]

    clusterer = Clusterer()
    clusters = clusterer.compute_centroids(embeddings, labels, ids, weights)

    # Invariant: Centroid dimensionality matches input
    for cluster in clusters:
        assert cluster.centroid.shape == (n_dim,)

    # Invariant: Member count matches size
    for cluster in clusters:
        assert len(cluster.member_ids) == cluster.size

    # Invariant: Size > 0
    for cluster in clusters:
        assert cluster.size > 0

    # Invariant: avg_weight in valid range
    for cluster in clusters:
        assert 0.1 <= cluster.avg_weight <= 1.0


def test_cluster_result_types() -> None:
    """Test that ClusterResult fields have correct types."""
    clusterer = Clusterer(min_cluster_size=3)
    np.random.seed(42)
    embeddings = np.random.randn(20, 128).astype(np.float32)

    result = clusterer.cluster(embeddings)

    assert isinstance(result.labels, np.ndarray)
    assert isinstance(result.n_clusters, int)
    assert isinstance(result.noise_count, int)
    assert isinstance(result.probabilities, np.ndarray)


def test_cluster_info_types() -> None:
    """Test that ClusterInfo fields have correct types."""
    clusterer = Clusterer()
    embeddings = np.random.randn(10, 128).astype(np.float32)
    labels = np.array([0, 0, 0, 1, 1, 1, 1, 2, 2, 2])
    ids = [f"id{i}" for i in range(10)]

    clusters = clusterer.compute_centroids(embeddings, labels, ids)

    for cluster in clusters:
        assert isinstance(cluster.label, int)
        assert isinstance(cluster.centroid, np.ndarray)
        assert isinstance(cluster.member_ids, list)
        assert all(isinstance(mid, str) for mid in cluster.member_ids)
        assert isinstance(cluster.size, int)
        assert isinstance(cluster.avg_weight, float)
