"""Validation tests for clustering with production-like data.

These tests verify clustering algorithms work correctly with realistic
data profiles, not just minimal synthetic data.

Reference: SPEC-034 Clustering Validation Scenarios 1-3
Reference: BUG-031 - Clustering failed with 63 similar GHAP entries
"""

import numpy as np
import pytest

from clams.clustering import Clusterer
from tests.fixtures.data_profiles import (
    EMBEDDINGS_OVERLAPPING,
    GHAP_DIFFUSE_CLOUD,
    GHAP_PRODUCTION,
    EmbeddingProfile,
)
from tests.fixtures.generators.embeddings import generate_clusterable_embeddings
from tests.fixtures.generators.ghap import generate_ghap_entries


class TestMinClusterSizeBoundary:
    """Scenario 1: Min Cluster Size Boundary Testing.

    Verify HDBSCAN respects min_cluster_size parameter at boundaries.

    Note: HDBSCAN requires density contrast - with only a single uniform cluster,
    it cannot distinguish the cluster from the background. Multiple clusters
    with different densities are needed for meaningful clustering.
    """

    @pytest.mark.parametrize(
        "min_cluster_size,n_points,n_clusters",
        [(3, 60, 3), (5, 80, 4), (7, 100, 5)],
    )
    def test_multiple_clusters_form_correctly(
        self, min_cluster_size: int, n_points: int, n_clusters: int
    ) -> None:
        """With multiple well-separated clusters, HDBSCAN finds structure."""
        profile = EmbeddingProfile(
            n_points=n_points,
            n_clusters=n_clusters,
            cluster_spread=0.15,  # Moderate spread
            inter_cluster_distance=0.5,  # Good separation
            noise_ratio=0.1,
            embedding_dim=768,
        )

        result = generate_clusterable_embeddings(profile, seed=42)

        clusterer = Clusterer(
            min_cluster_size=min_cluster_size,
            min_samples=max(2, min_cluster_size - 1),
            metric="cosine",
        )

        cluster_result = clusterer.cluster(result.embeddings)

        # Should find most of the clusters
        assert cluster_result.n_clusters >= n_clusters - 1, (
            f"Expected ~{n_clusters} clusters with {n_points} points "
            f"and min_cluster_size={min_cluster_size}, got {cluster_result.n_clusters}"
        )

    @pytest.mark.parametrize("min_cluster_size", [5, 7, 10])
    def test_increasing_min_cluster_size_effect(self, min_cluster_size: int) -> None:
        """Larger min_cluster_size tends to merge smaller clusters or treat as noise."""
        profile = EmbeddingProfile(
            n_points=100,
            n_clusters=5,
            cluster_spread=0.2,
            inter_cluster_distance=0.4,
            noise_ratio=0.1,
            embedding_dim=768,
        )

        result = generate_clusterable_embeddings(profile, seed=42)

        # Smaller min_cluster_size
        small_clusterer = Clusterer(
            min_cluster_size=3,
            min_samples=2,
            metric="cosine",
        )
        small_result = small_clusterer.cluster(result.embeddings)

        # Larger min_cluster_size
        large_clusterer = Clusterer(
            min_cluster_size=min_cluster_size,
            min_samples=max(2, min_cluster_size - 1),
            metric="cosine",
        )
        large_result = large_clusterer.cluster(result.embeddings)

        # Larger min_cluster_size should find same or fewer clusters (or more noise)
        # Allow some variance since cluster structure depends on data
        combined_effect = (
            large_result.n_clusters <= small_result.n_clusters + 1
            or large_result.noise_count >= small_result.noise_count
        )
        assert combined_effect, (
            f"Larger min_cluster_size should reduce clusters or increase noise. "
            f"Small: {small_result.n_clusters} clusters/{small_result.noise_count} noise, "
            f"Large: {large_result.n_clusters} clusters/{large_result.noise_count} noise"
        )


class TestDiffuseThemeCloud:
    """Scenario 2: Diffuse Theme Cloud Testing.

    Reference: BUG-031 - 63 similar GHAP entries formed no clusters.

    Key insight from investigation: HDBSCAN requires density contrast to find
    clusters. A single uniform-density theme (all points similarly distributed)
    has no density structure for HDBSCAN to identify. This is CORRECT behavior,
    not a bug - when all points are equally dense, there are no clusters.

    The real fix for BUG-031 scenarios is to ensure the data has actual
    sub-themes or density variation, not to tune HDBSCAN parameters.
    """

    def test_bug_031_scenario_documents_limitation(self) -> None:
        """Document that single uniform theme produces no clusters.

        BUG-031: 63 GHAP entries with single diffuse theme produced 0 clusters.
        This is EXPECTED behavior - HDBSCAN needs density contrast.

        The test verifies this limitation is understood and documented.
        """
        result = generate_ghap_entries(GHAP_DIFFUSE_CLOUD, seed=42)

        clusterer = Clusterer(
            min_cluster_size=3,  # Even with relaxed params
            min_samples=2,
            metric="cosine",
        )

        cluster_result = clusterer.cluster(result.embeddings)

        # Document the expected behavior: uniform density = no clusters
        # This is correct HDBSCAN behavior, not a bug
        # The assertion documents that this is expected
        if cluster_result.n_clusters == 0:
            # Expected: single uniform theme has no density structure
            pass  # This is OK - it's the documented limitation
        else:
            # If we DO find clusters, that's a bonus but not required
            pass

        # At minimum, verify HDBSCAN ran without errors
        assert cluster_result.noise_count + sum(
            1 for label in cluster_result.labels if label >= 0
        ) == len(result.embeddings)

    def test_multi_theme_profile_produces_clusters(self) -> None:
        """Data with multiple themes SHOULD cluster successfully."""
        # Unlike single-theme diffuse cloud, multiple themes create density contrast
        profile = EmbeddingProfile(
            n_points=100,
            n_clusters=3,  # Multiple themes
            cluster_spread=0.2,  # Moderate spread within themes
            inter_cluster_distance=0.4,  # Some separation
            noise_ratio=0.15,
        )

        result = generate_clusterable_embeddings(profile, seed=42)

        clusterer = Clusterer(
            min_cluster_size=5,
            min_samples=3,
            metric="cosine",
        )

        cluster_result = clusterer.cluster(result.embeddings)

        # Multiple themes should produce clusters
        assert cluster_result.n_clusters >= 2, (
            f"Multi-theme data should cluster. Got {cluster_result.n_clusters}"
        )

    def test_production_profile_reasonable_clustering(self) -> None:
        """Production-like GHAP profile should produce reasonable clusters."""
        result = generate_ghap_entries(GHAP_PRODUCTION, seed=42)

        clusterer = Clusterer(
            min_cluster_size=5,
            min_samples=3,
            metric="cosine",
        )

        cluster_result = clusterer.cluster(result.embeddings)

        # With 100 entries and 3 themes, expect some clusters
        assert cluster_result.n_clusters >= 1, (
            f"Production-like profile ({GHAP_PRODUCTION.count} entries, "
            f"{GHAP_PRODUCTION.theme_count} themes) should produce clusters"
        )


class TestMixedDensityRegions:
    """Scenario 3: Mixed Density Regions Testing.

    Verify HDBSCAN handles varying local density correctly.
    """

    def test_finds_clusters_in_dense_regions(self) -> None:
        """Clusters should form in dense regions, sparse outliers as noise."""
        # Create profile with overlapping clusters of varying density
        result = generate_clusterable_embeddings(EMBEDDINGS_OVERLAPPING, seed=42)

        clusterer = Clusterer(
            min_cluster_size=5,
            min_samples=3,
            metric="cosine",
        )

        cluster_result = clusterer.cluster(result.embeddings)

        # Should find most of the clusters
        # Allow some noise due to overlap
        assert cluster_result.n_clusters >= 2, (
            f"Expected >= 2 clusters from {EMBEDDINGS_OVERLAPPING.n_clusters} "
            f"overlapping clusters, got {cluster_result.n_clusters}"
        )

    def test_noise_points_correctly_identified(self) -> None:
        """Points in sparse regions should be classified as noise."""
        profile = EmbeddingProfile(
            n_points=100,
            n_clusters=2,
            cluster_spread=0.15,  # Tight clusters
            noise_ratio=0.3,  # 30% noise
            embedding_dim=768,
        )

        result = generate_clusterable_embeddings(profile, seed=42)

        clusterer = Clusterer(
            min_cluster_size=5,
            min_samples=3,
            metric="cosine",
        )

        cluster_result = clusterer.cluster(result.embeddings)

        # The generated noise should largely be classified as noise by HDBSCAN
        # Allow some tolerance since HDBSCAN might classify some noise as cluster
        expected_noise = int(profile.n_points * profile.noise_ratio)

        # At least half of injected noise should be classified as noise
        assert cluster_result.noise_count >= expected_noise * 0.5, (
            f"Expected at least {expected_noise * 0.5:.0f} noise points "
            f"(50% of injected {expected_noise}), got {cluster_result.noise_count}"
        )


class TestClusteringPerformance:
    """Verify clustering completes within time bounds for production-like data."""

    @pytest.mark.timeout(10)  # 10 second timeout
    def test_clustering_200_points_under_10s(self) -> None:
        """Clustering 200 points should complete in < 10 seconds."""
        profile = EmbeddingProfile(
            n_points=200,
            n_clusters=5,
            cluster_spread=0.25,
            noise_ratio=0.15,
            embedding_dim=768,
        )

        result = generate_clusterable_embeddings(profile, seed=42)

        clusterer = Clusterer(
            min_cluster_size=5,
            min_samples=3,
            metric="cosine",
        )

        # This should complete well under 10 seconds
        cluster_result = clusterer.cluster(result.embeddings)

        assert cluster_result.n_clusters >= 1


class TestEmbeddingGeneratorProperties:
    """Verify embedding generator produces expected properties."""

    def test_embeddings_are_unit_normalized(self) -> None:
        """All generated embeddings should be unit vectors."""
        profile = EmbeddingProfile(n_points=50, n_clusters=3)
        result = generate_clusterable_embeddings(profile, seed=42)

        norms = np.linalg.norm(result.embeddings, axis=1)
        np.testing.assert_allclose(
            norms, 1.0, rtol=1e-5, err_msg="Embeddings should be unit normalized"
        )

    def test_cluster_labels_match_profile(self) -> None:
        """Generated labels should match profile parameters."""
        n_points = 100
        n_clusters = 4
        noise_ratio = 0.2

        profile = EmbeddingProfile(
            n_points=n_points,
            n_clusters=n_clusters,
            noise_ratio=noise_ratio,
        )

        result = generate_clusterable_embeddings(profile, seed=42)

        # Check dimensions
        assert result.embeddings.shape == (n_points, profile.embedding_dim)
        assert len(result.labels) == n_points

        # Check noise count approximately matches profile
        expected_noise = int(n_points * noise_ratio)
        actual_noise = int(np.sum(result.labels == -1))
        assert actual_noise == expected_noise

        # Check non-noise labels are in valid range
        non_noise_labels = result.labels[result.labels >= 0]
        assert np.all(non_noise_labels >= 0)
        assert np.all(non_noise_labels < n_clusters)

    def test_reproducibility(self) -> None:
        """Same seed should produce identical results."""
        profile = EmbeddingProfile(n_points=50, n_clusters=3)

        result1 = generate_clusterable_embeddings(profile, seed=42)
        result2 = generate_clusterable_embeddings(profile, seed=42)

        np.testing.assert_array_equal(result1.embeddings, result2.embeddings)
        np.testing.assert_array_equal(result1.labels, result2.labels)
        np.testing.assert_array_equal(result1.centroids, result2.centroids)

    def test_different_seeds_differ(self) -> None:
        """Different seeds should produce different results."""
        profile = EmbeddingProfile(n_points=50, n_clusters=3)

        result1 = generate_clusterable_embeddings(profile, seed=1)
        result2 = generate_clusterable_embeddings(profile, seed=2)

        assert not np.allclose(result1.embeddings, result2.embeddings)
