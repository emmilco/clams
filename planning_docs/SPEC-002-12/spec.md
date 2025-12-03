# SPEC-002-12: Clusterer HDBSCAN

## Overview

Implement HDBSCAN clustering for experience embeddings to discover emergent patterns in agent behavior. The Clusterer module groups similar experiences along multiple axes and computes cluster centroids for value formation.

## Dependencies

### Completed
- SPEC-002-02: EmbeddingService
- SPEC-002-03: VectorStore

### Required
- hdbscan (separate package, NOT part of scikit-learn)
- numpy

## Components

### Clusterer

**Purpose**: Apply HDBSCAN clustering to embeddings and compute weighted centroids.

**Interface**:
```python
from dataclasses import dataclass
from typing import List

import numpy as np

@dataclass
class ClusterResult:
    """Result from clustering operation."""
    labels: np.ndarray           # Cluster labels (same length as input)
    n_clusters: int              # Number of clusters found (-1 = noise)
    noise_count: int             # Number of points labeled as noise (-1)
    probabilities: np.ndarray    # Cluster membership probabilities

@dataclass
class ClusterInfo:
    """Information about a single cluster."""
    label: int                   # Cluster label (0, 1, 2, ...)
    centroid: np.ndarray         # Weighted centroid vector
    member_ids: List[str]        # IDs of members in this cluster
    size: int                    # Number of members
    avg_weight: float            # Average weight of members

class Clusterer:
    """HDBSCAN clustering with weighted centroids."""

    def __init__(
        self,
        min_cluster_size: int = 5,
        min_samples: int = 3,
        metric: str = "cosine",
        cluster_selection_method: str = "eom",
    ):
        """
        Initialize clusterer with HDBSCAN parameters.

        Args:
            min_cluster_size: Minimum size of a cluster (default: 5)
            min_samples: Conservative parameter for core points (default: 3)
            metric: Distance metric (default: "cosine")
            cluster_selection_method: "eom" (Excess of Mass) or "leaf"
        """
        pass

    def cluster(
        self,
        embeddings: np.ndarray,
        weights: np.ndarray | None = None,
    ) -> ClusterResult:
        """
        Cluster embeddings using HDBSCAN.

        Args:
            embeddings: Array of shape (n_samples, n_dimensions)
            weights: Optional weights for each embedding (default: all 1.0)
                     Higher weights = more influence on centroids

        Returns:
            ClusterResult with labels, counts, and probabilities

        Raises:
            ValueError: If embeddings array is invalid (empty, wrong shape)
            ValueError: If weights length doesn't match embeddings
        """
        pass

    def compute_centroids(
        self,
        embeddings: np.ndarray,
        labels: np.ndarray,
        ids: List[str],
        weights: np.ndarray | None = None,
    ) -> List[ClusterInfo]:
        """
        Compute weighted centroids for each cluster.

        Args:
            embeddings: Array of shape (n_samples, n_dimensions)
            labels: Cluster labels from HDBSCAN (-1 = noise)
            ids: IDs corresponding to each embedding
            weights: Optional weights for weighted centroid computation

        Returns:
            List of ClusterInfo, one per cluster (excluding noise)
            Sorted by cluster label (0, 1, 2, ...)

        Raises:
            ValueError: If array shapes don't match
        """
        pass
```

### ExperienceClusterer

**Purpose**: Cluster experiences by axis using VectorStore retrieval.

**Interface**:
```python
from typing import Dict

class ExperienceClusterer:
    """Cluster experiences along multiple semantic axes."""

    def __init__(
        self,
        vector_store: VectorStore,
        clusterer: Clusterer,
    ):
        """
        Initialize experience clusterer.

        Args:
            vector_store: VectorStore instance with indexed experiences
            clusterer: Clusterer instance with HDBSCAN configuration
        """
        pass

    async def cluster_axis(self, axis: str) -> List[ClusterInfo]:
        """
        Cluster experiences along a single axis.

        Args:
            axis: Axis name, one of:
                  - "full" (complete narrative)
                  - "strategy" (systematic-elimination, etc.)
                  - "surprise" (unexpected outcomes)
                  - "root_cause" (why hypothesis was wrong)

                  Note: "domain" is NOT a clustering axis. Domain is metadata on
                  experiences that can be used to filter the "full" axis before
                  clustering, but domain itself is not clustered independently.

        Returns:
            List of ClusterInfo for each cluster found

        Steps:
            1. Retrieve all embeddings for axis from VectorStore
            2. Extract weights from confidence tiers:
               - gold: 1.0
               - silver: 0.8
               - bronze: 0.5
               - abandoned: 0.2
               - missing/invalid: 0.5 (default to bronze weight)
            3. Run HDBSCAN clustering
            4. Compute weighted centroids
            5. Return ClusterInfo list

        Raises:
            ValueError: If axis is invalid
            ValueError: If no embeddings found for axis (collection empty)
        """
        pass

    async def cluster_all_axes(self) -> Dict[str, List[ClusterInfo]]:
        """
        Cluster experiences on all axes.

        Returns:
            Dict mapping axis name to list of ClusterInfo
            Example: {"full": [...], "domain": [...], "strategy": [...]}

        Notes:
            - Axes with no data are omitted from result (not empty lists)
            - Each axis clustered independently with same parameters
        """
        pass
```

## VectorStore Collection Structure

Experiences are stored in VectorStore with these collections:

```python
# Collection names by axis (4 axes total)
# Note: "domain" is a metadata filter on experiences_full, not a separate axis
AXIS_COLLECTIONS = {
    "full": "experiences_full",
    "strategy": "experiences_strategy",
    "surprise": "experiences_surprise",
    "root_cause": "experiences_root_cause",
}

# Payload structure for each embedding
{
    "id": str,                    # GHAP entry ID
    "confidence_tier": str,       # "gold", "silver", "bronze", "abandoned"
    "created_at": str,            # ISO timestamp (UTC)
    "session_id": str,            # Session identifier
    # ... additional metadata fields ...
}
```

## Confidence Tier Weights

Weights are derived from confidence tiers:

| Tier | Weight | Rationale |
|------|--------|-----------|
| Gold | 1.0 | Auto-captured outcomes, highest quality |
| Silver | 0.8 | Manual resolution, good quality |
| Bronze | 0.5 | Poor quality (tautologies, vague) |
| Abandoned | 0.2 | Incomplete, low signal |

Weights affect:
- **Centroid computation**: Higher-weighted points pull centroids closer
- **Cluster influence**: Gold experiences have more impact on cluster shape

## HDBSCAN Parameters

Default configuration:

```python
min_cluster_size = 5      # Minimum viable cluster size
min_samples = 3           # Conservative core point detection
metric = "cosine"         # Semantic similarity metric
cluster_selection_method = "eom"  # Excess of Mass (more stable)
```

### Parameter Rationale

**min_cluster_size=5**: Ensures clusters represent meaningful patterns, not noise. Smaller values risk over-clustering.

**min_samples=3**: Conservative setting that prioritizes precision over recall. Prevents spurious clusters from random noise.

**metric="cosine"**: Standard for semantic embeddings. Measures angular similarity, invariant to vector magnitude.

**cluster_selection_method="eom"**: Excess of Mass selection is more stable than "leaf" method for sparse data. Prefers larger, more stable clusters.

## Weighted Centroid Calculation

For a cluster with members `{e₁, e₂, ..., eₙ}` and weights `{w₁, w₂, ..., wₙ}`:

```
centroid = Σ(wᵢ * eᵢ) / Σ(wᵢ)
```

This ensures:
- Gold experiences (weight=1.0) pull centroids closer to themselves
- Bronze experiences (weight=0.5) have half the influence
- Centroid represents weighted semantic center of the cluster

## Performance Requirements

### Latency Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| cluster() | <1s for 500 points | HDBSCAN on typical experience dataset |
| compute_centroids() | <100ms | Simple weighted average |
| cluster_axis() | <2s | Includes VectorStore retrieval + clustering |
| cluster_all_axes() | <8s | 4 axes * 2s each, some parallel potential |

### Scalability

- **Expected scale**: 100-1000 experiences per axis initially
- **HDBSCAN performance**: O(n log n) in practice
- **Memory**: ~100MB for 1000 embeddings (768-dim floats)
- **Batch processing**: All axes can be clustered in parallel if needed

## Testing Strategy

### Unit Tests

#### Clusterer Tests
```python
def test_cluster_basic():
    """Test clustering with simple synthetic data."""
    # Create 3 clear clusters in embedding space
    # Verify HDBSCAN finds all 3
    # Check noise label (-1) for outliers

def test_cluster_with_weights():
    """Test weighted clustering pulls centroids correctly."""
    # Create cluster with one high-weight outlier
    # Verify centroid shifts toward weighted point

def test_cluster_empty():
    """Test error handling for empty input."""
    # Should raise ValueError

def test_cluster_single_cluster():
    """Test behavior when all points form one cluster."""

def test_compute_centroids():
    """Test centroid computation with known data."""
    # Verify centroid is weighted mean
    # Check avg_weight calculation

def test_compute_centroids_excludes_noise():
    """Test that noise points (-1 label) are excluded."""
```

#### ExperienceClusterer Tests
```python
@pytest.mark.asyncio
async def test_cluster_axis_success(mock_vector_store):
    """Test successful clustering of one axis."""
    # Mock VectorStore to return fake embeddings
    # Verify ClusterInfo returned correctly

@pytest.mark.asyncio
async def test_cluster_axis_invalid():
    """Test error for invalid axis name."""
    # Should raise ValueError

@pytest.mark.asyncio
async def test_cluster_all_axes(mock_vector_store):
    """Test clustering all axes."""
    # Verify all axes processed
    # Check result structure

@pytest.mark.asyncio
async def test_cluster_axis_no_data(mock_vector_store):
    """Test behavior when axis collection is empty."""
    # Should raise ValueError with clear message
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_end_to_end_clustering(qdrant_container, embedding_service):
    """Test full clustering workflow with real Qdrant."""
    # Setup: Store 50 synthetic experiences in VectorStore
    # Cluster on "full" axis
    # Verify:
    #   - Clusters found
    #   - Centroids computed
    #   - Member IDs correct
    #   - Weights applied correctly

@pytest.mark.asyncio
async def test_multi_axis_clustering(qdrant_container, embedding_service):
    """Test clustering on multiple axes with same data."""
    # Verify different axes produce different clusters
    # Check all axes processed independently
```

### Property-Based Tests (Required)

Use `hypothesis` to verify clustering invariants hold for arbitrary inputs:

```python
from hypothesis import given, strategies as st

@given(
    n_points=st.integers(min_value=10, max_value=100),
    n_dim=st.integers(min_value=128, max_value=768),
)
def test_cluster_invariants(n_points, n_dim):
    """Test clustering invariants with arbitrary data."""
    embeddings = np.random.randn(n_points, n_dim).astype(np.float32)
    result = clusterer.cluster(embeddings)

    # Invariant: Every point gets a label
    assert len(result.labels) == n_points

    # Invariant: n_clusters <= n_points
    assert result.n_clusters <= n_points

    # Invariant: Probabilities in [0, 1]
    assert np.all((result.probabilities >= 0) & (result.probabilities <= 1))

@given(
    n_points=st.integers(min_value=10, max_value=100),
    weights=st.lists(st.floats(min_value=0.1, max_value=1.0), min_size=10, max_size=100),
)
def test_centroid_invariants(n_points, weights):
    """Test centroid computation invariants."""
    n_dim = 128
    embeddings = np.random.randn(n_points, n_dim).astype(np.float32)
    weights_array = np.array(weights[:n_points])
    labels = np.random.randint(0, 5, size=n_points)  # 5 clusters
    ids = [f"id_{i}" for i in range(n_points)]

    clusters = clusterer.compute_centroids(embeddings, labels, ids, weights_array)

    # Invariant: Centroid dimensionality matches input
    for cluster in clusters:
        assert cluster.centroid.shape == (n_dim,)

    # Invariant: Member count matches size
    for cluster in clusters:
        assert len(cluster.member_ids) == cluster.size
```

## Acceptance Criteria

### Functional
1. ✅ Clusterer can cluster embeddings with HDBSCAN
2. ✅ Clusterer computes weighted centroids correctly
3. ✅ Noise points (-1 label) excluded from clusters
4. ✅ ExperienceClusterer retrieves embeddings from VectorStore
5. ✅ ExperienceClusterer applies confidence tier weights (gold=1.0, silver=0.8, bronze=0.5, abandoned=0.2)
6. ✅ ExperienceClusterer clusters all 4 axes independently
7. ✅ cluster_all_axes() returns dict with all axes
8. ✅ Empty collections handled gracefully (raise ValueError)
9. ✅ Invalid axis name raises ValueError
10. ✅ ClusterInfo includes all required fields

### Quality
1. ✅ Centroid computation is numerically stable
2. ✅ Weight normalization prevents overflow/underflow
3. ✅ Cluster labels are consistent (0, 1, 2, ...)
4. ✅ Member IDs correctly associated with clusters
5. ✅ Error messages are clear and actionable
6. ✅ Type hints for all public APIs
7. ✅ Docstrings for all classes and methods

### Performance
1. ✅ Clustering 500 points completes in <1s
2. ✅ Centroid computation completes in <100ms
3. ✅ cluster_all_axes() completes in <8s
4. ✅ Peak memory usage ≤150MB for 1000 embeddings (768-dim)
5. ✅ No memory leaks with repeated clustering

### Testing
1. ✅ Unit test coverage ≥ 90%
2. ✅ Integration tests with real Qdrant
3. ✅ All error cases tested
4. ✅ Type checking passes (mypy --strict)
5. ✅ Linting passes (ruff)

## Out of Scope

- Value formation (SPEC-002-13)
- Value validation via centroid distance
- Cluster visualization
- Incremental clustering (full recompute each time)
- Parameter tuning UI
- Cluster stability metrics
- Cross-axis cluster correlation

## Notes

- HDBSCAN is hierarchical and density-based, so cluster count is automatic
- Noise points (-1 label) are normal and expected for outliers
- Cosine metric works well for normalized embeddings
- Weights only affect centroid computation, not HDBSCAN algorithm itself
- Each of the 4 axes is clustered independently (no cross-axis constraints)
- All async operations use `await` consistently
- Logging via `structlog` following existing codebase patterns
