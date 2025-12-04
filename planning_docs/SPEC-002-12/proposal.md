# Technical Proposal: Clusterer HDBSCAN

## Problem Statement

The Learning Memory Server needs to discover emergent patterns in agent experiences. Raw experiences (GHAP entries) are stored as embeddings across multiple axes (full narrative, domain, strategy, surprise, root cause). To enable value formation, we must:

1. **Group similar experiences** - Cluster embeddings to find coherent patterns
2. **Weight by quality** - High-confidence experiences should influence clusters more
3. **Compute centroids** - Find semantic center of each cluster for validation
4. **Scale to multiple axes** - Cluster independently on each semantic dimension
5. **Handle noise** - Gracefully exclude outliers that don't fit patterns

## Proposed Solution

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                       ExperienceClusterer                            │
│  (Orchestrates clustering across multiple axes)                     │
└────────────┬────────────────────────────────────────────────────────┘
             │
             │ For each axis (full, domain, strategy, surprise, root_cause):
             │
             ├──> 1. Retrieve embeddings + metadata from VectorStore
             │
             ├──> 2. Extract confidence tier weights (gold=1.0, silver=0.8, etc.)
             │
             ├──> 3. Pass to Clusterer
             │
             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          Clusterer                                   │
│  (HDBSCAN clustering + weighted centroid computation)                │
└─────────────────────────────────────────────────────────────────────┘
             │
             ├──> 4. Run HDBSCAN (density-based clustering)
             │       - Returns labels (-1 = noise, 0, 1, 2, ... = clusters)
             │       - Returns membership probabilities
             │
             ├──> 5. Compute weighted centroids per cluster
             │       - centroid = Σ(weight * embedding) / Σ(weight)
             │       - Exclude noise points (-1)
             │
             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       ClusterInfo Results                            │
│  (label, centroid, member_ids, size, avg_weight)                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Module Structure

```
clustering/
├── __init__.py          # Public exports
├── clusterer.py         # Clusterer class (HDBSCAN + centroids)
├── experience.py        # ExperienceClusterer class
└── types.py             # ClusterResult, ClusterInfo dataclasses, weight mappings
```

**Public exports** (`__init__.py`):
```python
"""Clustering module for experience pattern discovery."""

from .clusterer import Clusterer
from .experience import ExperienceClusterer
from .types import ClusterResult, ClusterInfo, CONFIDENCE_WEIGHTS, get_weight

__all__ = [
    "Clusterer",
    "ExperienceClusterer",
    "ClusterResult",
    "ClusterInfo",
    "CONFIDENCE_WEIGHTS",
    "get_weight",
]
```

## Key Design Decisions

### 1. HDBSCAN Over K-Means

**Why HDBSCAN:**
- **Automatic cluster count** - No need to specify k upfront
- **Density-based** - Handles variable cluster sizes and shapes
- **Noise detection** - Outliers labeled -1, not forced into clusters
- **Hierarchical** - Can explore cluster tree if needed later

**Why not K-Means:**
- Requires knowing cluster count in advance
- Assumes spherical clusters of similar size
- Forces every point into a cluster (no noise concept)
- Poor performance on semantic embeddings with variable density

**Why not DBSCAN:**
- HDBSCAN is a hierarchical extension of DBSCAN
- Better at varying density clusters
- More stable parameter selection (min_cluster_size vs epsilon)

### 2. Cosine Metric for Semantic Similarity

```python
metric = "cosine"  # Angular similarity, invariant to magnitude
```

**Rationale:**
- Standard for embedding similarity
- Captures semantic relatedness (angle, not distance)
- Invariant to vector magnitude (normalized vs unnormalized embeddings)
- Compatible with VectorStore search (also uses cosine)

**Alternative considered:**
- Euclidean: More sensitive to magnitude differences, less semantic

### 3. Weighted Centroids

```python
def compute_weighted_centroid(
    embeddings: np.ndarray,
    weights: np.ndarray,
) -> np.ndarray:
    """
    Compute weighted centroid.

    centroid = Σ(wᵢ * eᵢ) / Σ(wᵢ)
    """
    weighted_sum = np.sum(embeddings * weights[:, np.newaxis], axis=0)
    weight_sum = np.sum(weights)
    return weighted_sum / weight_sum
```

**Rationale:**
- **Quality-aware**: Gold experiences (weight=1.0) pull centroids closer
- **Noise-resistant**: Bronze/abandoned experiences (weight ≤ 0.5) have less influence
- **Mathematically simple**: Weighted mean is interpretable and stable
- **Validation-ready**: Centroid represents semantic center for value validation

**Note on HDBSCAN weights:** HDBSCAN itself doesn't use weights—it clusters based on density alone. Weights only affect centroid computation. This is intentional: we want natural clustering first, then quality-weighted centroids.

### 4. Confidence Tier Weighting

```python
# types.py
CONFIDENCE_WEIGHTS = {
    "gold": 1.0,
    "silver": 0.8,
    "bronze": 0.5,
    "abandoned": 0.2,
}

def get_weight(tier: str | None) -> float:
    """
    Get weight for confidence tier.

    Args:
        tier: Confidence tier string or None

    Returns:
        Weight value (0.2-1.0), defaults to 0.5 (bronze) for None/invalid
    """
    if tier is None:
        return 0.5  # Default to bronze weight
    return CONFIDENCE_WEIGHTS.get(tier.lower(), 0.5)  # Default: bronze
```

**Weight Rationale:**

| Tier | Weight | Why |
|------|--------|-----|
| Gold | 1.0 | Auto-captured, highest quality, full trust |
| Silver | 0.8 | Manual resolution, good quality, slight discount |
| Bronze | 0.5 | Poor quality (tautology, vague), half influence |
| Abandoned | 0.2 | Incomplete data, low signal |

**Design note:** Weights affect centroids but not clustering. A cluster of all bronze experiences is still valid—it just gets a centroid representing bronze-quality thinking.

### 5. Multi-Axis Independence

```python
async def cluster_all_axes(self) -> Dict[str, List[ClusterInfo]]:
    """Cluster each axis independently."""
    results = {}
    for axis in AXES:
        try:
            results[axis] = await self.cluster_axis(axis)
        except ValueError:
            # Skip axes with no data
            continue
    return results
```

**Rationale:**
- Each axis represents a different semantic dimension
- Cross-axis constraints would reduce pattern discovery
- Independent clustering allows different granularities per axis
- Simpler implementation and testing

**Future:** Could add cross-axis correlation analysis if patterns emerge.

## Implementation Details

### Clusterer Class

```python
# clustering/clusterer.py

from dataclasses import dataclass
from typing import List

import numpy as np
import hdbscan

from .types import ClusterResult, ClusterInfo


class Clusterer:
    """HDBSCAN clustering with weighted centroids."""

    def __init__(
        self,
        min_cluster_size: int = 5,
        min_samples: int = 3,
        metric: str = "cosine",
        cluster_selection_method: str = "eom",
    ):
        """Initialize with HDBSCAN parameters."""
        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples
        self.metric = metric
        self.cluster_selection_method = cluster_selection_method

    def cluster(
        self,
        embeddings: np.ndarray,
        weights: np.ndarray | None = None,
    ) -> ClusterResult:
        """Cluster embeddings using HDBSCAN."""
        if embeddings.size == 0:
            raise ValueError("Embeddings array is empty")

        if embeddings.ndim != 2:
            raise ValueError(
                f"Embeddings must be 2D array, got {embeddings.ndim}D"
            )

        if weights is not None and len(weights) != len(embeddings):
            raise ValueError(
                f"Weights length ({len(weights)}) doesn't match "
                f"embeddings ({len(embeddings)})"
            )

        # Create fresh HDBSCAN instance (avoids state reuse issues)
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            min_samples=self.min_samples,
            metric=self.metric,
            cluster_selection_method=self.cluster_selection_method,
        )

        # Run HDBSCAN
        labels = clusterer.fit_predict(embeddings)
        probabilities = clusterer.probabilities_

        # Count clusters (excluding noise = -1)
        unique_labels = set(labels)
        unique_labels.discard(-1)  # Remove noise label
        n_clusters = len(unique_labels)

        # Count noise points
        noise_count = np.sum(labels == -1)

        return ClusterResult(
            labels=labels,
            n_clusters=n_clusters,
            noise_count=noise_count,
            probabilities=probabilities,
        )

    def compute_centroids(
        self,
        embeddings: np.ndarray,
        labels: np.ndarray,
        ids: List[str],
        weights: np.ndarray | None = None,
    ) -> List[ClusterInfo]:
        """Compute weighted centroids for each cluster."""
        if len(embeddings) != len(labels) or len(embeddings) != len(ids):
            raise ValueError(
                f"Array lengths don't match: embeddings={len(embeddings)}, "
                f"labels={len(labels)}, ids={len(ids)}"
            )

        if weights is None:
            weights = np.ones(len(embeddings))

        if len(weights) != len(embeddings):
            raise ValueError(
                f"Weights length ({len(weights)}) doesn't match "
                f"embeddings ({len(embeddings)})"
            )

        # Get unique cluster labels (excluding noise = -1)
        unique_labels = sorted(set(labels))
        if -1 in unique_labels:
            unique_labels.remove(-1)

        clusters = []
        for label in unique_labels:
            # Get members of this cluster
            mask = labels == label
            cluster_embeddings = embeddings[mask]
            cluster_weights = weights[mask]
            cluster_ids = [ids[i] for i in np.where(mask)[0]]

            # Compute weighted centroid
            weighted_sum = np.sum(
                cluster_embeddings * cluster_weights[:, np.newaxis],
                axis=0
            )
            weight_sum = np.sum(cluster_weights)
            centroid = weighted_sum / weight_sum

            # Create ClusterInfo
            clusters.append(
                ClusterInfo(
                    label=int(label),
                    centroid=centroid,
                    member_ids=cluster_ids,
                    size=len(cluster_ids),
                    avg_weight=float(np.mean(cluster_weights)),
                )
            )

        return clusters
```

### ExperienceClusterer Class

```python
# clustering/experience.py

from typing import Dict, List

import numpy as np

from ..storage.base import VectorStore
from .clusterer import Clusterer
from .types import ClusterInfo, get_weight

# VectorStore collection names by axis
# Note: "domain" is not a clustering axis (it's metadata on experiences_full)
AXIS_COLLECTIONS = {
    "full": "experiences_full",
    "strategy": "experiences_strategy",
    "surprise": "experiences_surprise",
    "root_cause": "experiences_root_cause",
}


class ExperienceClusterer:
    """Cluster experiences along multiple semantic axes."""

    def __init__(self, vector_store: VectorStore, clusterer: Clusterer):
        """Initialize with VectorStore and Clusterer."""
        self.vector_store = vector_store
        self.clusterer = clusterer

    async def cluster_axis(self, axis: str) -> List[ClusterInfo]:
        """Cluster experiences along a single axis."""
        if axis not in AXIS_COLLECTIONS:
            raise ValueError(
                f"Invalid axis: {axis}. "
                f"Valid axes: {list(AXIS_COLLECTIONS.keys())}"
            )

        collection = AXIS_COLLECTIONS[axis]

        # Retrieve all embeddings from VectorStore
        # Using scroll() to get all points (no search query)
        # Note: If >10k experiences exist, implement pagination in future
        results = await self.vector_store.scroll(
            collection=collection,
            limit=10000,  # Hardcoded limit - warn if approaching
            with_vectors=True,
        )

        # Warn if we hit the limit (may indicate truncated dataset)
        if len(results) == 10000:
            import structlog
            logger = structlog.get_logger(__name__)
            logger.warning(
                "clustering.scroll_limit_reached",
                axis=axis,
                collection=collection,
                count=10000,
                message="May have truncated results - consider pagination"
            )

        if not results:
            raise ValueError(
                f"No embeddings found for axis '{axis}' "
                f"(collection: {collection})"
            )

        # Extract data from results
        embeddings = np.array([r.vector for r in results], dtype=np.float32)
        ids = [r.id for r in results]
        tiers = [r.payload.get("confidence_tier", "bronze") for r in results]
        weights = np.array([get_weight(tier) for tier in tiers])

        # Cluster
        cluster_result = self.clusterer.cluster(embeddings, weights)

        # Check for all-noise result (no clusters found)
        if cluster_result.n_clusters == 0:
            import structlog
            logger = structlog.get_logger(__name__)
            logger.warning(
                "clustering.all_noise",
                axis=axis,
                total_points=len(embeddings),
                noise_count=cluster_result.noise_count,
                message="HDBSCAN labeled all points as noise - no clusters found"
            )
            return []  # Return empty list if no clusters

        # Compute centroids
        clusters = self.clusterer.compute_centroids(
            embeddings=embeddings,
            labels=cluster_result.labels,
            ids=ids,
            weights=weights,
        )

        return clusters

    async def cluster_all_axes(self) -> Dict[str, List[ClusterInfo]]:
        """Cluster experiences on all axes."""
        results = {}
        for axis in AXIS_COLLECTIONS.keys():
            try:
                results[axis] = await self.cluster_axis(axis)
            except ValueError:
                # Skip axes with no data
                # Log warning but don't fail entire operation
                continue

        return results
```

### Type Definitions

```python
# clustering/types.py

from dataclasses import dataclass
from typing import List

import numpy as np


@dataclass
class ClusterResult:
    """Result from clustering operation."""

    labels: np.ndarray           # Cluster labels (same length as input)
    n_clusters: int              # Number of clusters found
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


# Confidence tier weight mappings
CONFIDENCE_WEIGHTS = {
    "gold": 1.0,
    "silver": 0.8,
    "bronze": 0.5,
    "abandoned": 0.2,
}


def get_weight(tier: str | None) -> float:
    """
    Get weight for confidence tier.

    Args:
        tier: Confidence tier string or None

    Returns:
        Weight value (0.2-1.0), defaults to 0.5 (bronze) for None/invalid
    """
    if tier is None:
        return 0.5  # Default to bronze weight
    return CONFIDENCE_WEIGHTS.get(tier.lower(), 0.5)  # Default: bronze
```

## Parameter Selection

### HDBSCAN Parameters

```python
min_cluster_size = 5      # Minimum viable cluster size
min_samples = 3           # Conservative core point detection
metric = "cosine"         # Semantic similarity
cluster_selection_method = "eom"  # Excess of Mass
```

**min_cluster_size=5:**
- Too low (e.g., 2-3): Over-clustering, many spurious patterns
- Too high (e.g., 10+): Under-clustering, miss valid small patterns
- 5 is a sweet spot: Enough signal to be meaningful, not overly conservative

**min_samples=3:**
- Controls strictness of core point definition
- Lower values (1-2): More points considered core, looser clusters
- Higher values (5+): Fewer core points, tighter clusters, more noise
- 3 balances precision and recall

**cluster_selection_method="eom":**
- "eom" (Excess of Mass): Prefers clusters with high excess of density over background
- "leaf": More granular, can produce many small clusters
- For sparse experience data, "eom" is more stable

### Tuning Strategy

Initial deployment uses defaults. If clustering quality is poor:

1. **Too many small clusters:** Increase `min_cluster_size` to 7-10
2. **Too much noise:** Decrease `min_samples` to 2
3. **Too few clusters:** Decrease `min_cluster_size` to 3-4
4. **Unstable clusters:** Keep "eom", or try "leaf" for finer granularity

## Testing Strategy

### Unit Tests

```python
# tests/clustering/test_clusterer.py

import numpy as np
import pytest

from learning_memory_server.clustering import Clusterer, ClusterResult


def test_cluster_basic():
    """Test clustering with synthetic data."""
    clusterer = Clusterer(min_cluster_size=3)

    # Create 2 clear clusters in 2D space
    cluster1 = np.random.randn(10, 2) + np.array([0, 0])
    cluster2 = np.random.randn(10, 2) + np.array([10, 10])
    embeddings = np.vstack([cluster1, cluster2]).astype(np.float32)

    result = clusterer.cluster(embeddings)

    assert isinstance(result, ClusterResult)
    assert result.n_clusters >= 1  # At least one cluster
    assert len(result.labels) == 20
    assert result.noise_count >= 0


def test_cluster_with_weights():
    """Test weighted centroid computation."""
    clusterer = Clusterer(min_cluster_size=3)

    # Simple 2D cluster
    embeddings = np.array([
        [0, 0],
        [1, 1],
        [0.5, 0.5],
    ], dtype=np.float32)

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


def test_cluster_empty():
    """Test error handling for empty input."""
    clusterer = Clusterer()
    empty = np.array([]).reshape(0, 128).astype(np.float32)

    with pytest.raises(ValueError, match="empty"):
        clusterer.cluster(empty)


def test_compute_centroids_excludes_noise():
    """Test that noise points are excluded."""
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
```

```python
# tests/clustering/test_experience.py

import numpy as np
import pytest

from learning_memory_server.clustering import (
    Clusterer,
    ExperienceClusterer,
)
from learning_memory_server.storage.base import SearchResult


@pytest.mark.asyncio
async def test_cluster_axis_success(mock_vector_store):
    """Test successful clustering of one axis."""
    # Mock VectorStore.scroll() to return fake data
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


@pytest.mark.asyncio
async def test_cluster_axis_invalid():
    """Test error for invalid axis name."""
    clusterer = Clusterer()
    exp_clusterer = ExperienceClusterer(None, clusterer)

    with pytest.raises(ValueError, match="Invalid axis"):
        await exp_clusterer.cluster_axis("invalid_axis")


@pytest.mark.asyncio
async def test_cluster_axis_no_data(mock_vector_store):
    """Test behavior when axis collection is empty."""
    mock_vector_store.scroll.return_value = []

    clusterer = Clusterer()
    exp_clusterer = ExperienceClusterer(mock_vector_store, clusterer)

    with pytest.raises(ValueError, match="No embeddings found"):
        await exp_clusterer.cluster_axis("full")


@pytest.mark.asyncio
async def test_cluster_all_axes(mock_vector_store):
    """Test clustering all axes."""
    # Return different data for each axis
    def scroll_side_effect(collection, **kwargs):
        if "full" in collection:
            return [SearchResult(...) for _ in range(10)]
        elif "domain" in collection:
            return [SearchResult(...) for _ in range(15)]
        else:
            return []  # Other axes empty

    mock_vector_store.scroll.side_effect = scroll_side_effect

    clusterer = Clusterer(min_cluster_size=3)
    exp_clusterer = ExperienceClusterer(mock_vector_store, clusterer)

    results = await exp_clusterer.cluster_all_axes()

    # Should have results for axes with data
    assert "full" in results or "domain" in results
    # Empty axes omitted
    assert all(len(v) >= 0 for v in results.values())
```

### Integration Tests

```python
# tests/clustering/test_integration.py

import numpy as np
import pytest

from learning_memory_server.clustering import Clusterer, ExperienceClusterer
from learning_memory_server.storage.qdrant import QdrantVectorStore


@pytest.mark.asyncio
async def test_end_to_end_clustering(qdrant_container):
    """Test full clustering workflow with real Qdrant."""
    vector_store = QdrantVectorStore(url=qdrant_container.url)
    collection = "test_experiences_full"

    # Create collection
    await vector_store.create_collection(collection, dimension=128)

    # Store 50 synthetic experiences (3 clear clusters)
    for i in range(50):
        cluster_id = i // 17  # 3 clusters
        base = np.array([cluster_id * 10, 0, 0])
        vector = (np.random.randn(128) + base).astype(np.float32)

        await vector_store.upsert(
            collection=collection,
            id=f"ghap_{i}",
            vector=vector,
            payload={
                "confidence_tier": "gold" if i % 3 == 0 else "silver",
            },
        )

    # Cluster
    clusterer = Clusterer(min_cluster_size=5)
    exp_clusterer = ExperienceClusterer(vector_store, clusterer)

    # Override collection mapping for test
    exp_clusterer.AXIS_COLLECTIONS = {"full": collection}

    clusters = await exp_clusterer.cluster_axis("full")

    # Should find clusters (exact count depends on HDBSCAN)
    assert len(clusters) >= 1

    # Verify ClusterInfo structure
    for cluster in clusters:
        assert cluster.label >= 0
        assert cluster.size > 0
        assert len(cluster.member_ids) == cluster.size
        assert cluster.centroid.shape == (128,)
        assert 0.0 <= cluster.avg_weight <= 1.0
```

## Performance Considerations

### Expected Performance

| Dataset Size | Dimensions | Time (est) |
|--------------|------------|------------|
| 100 points | 768 | <100ms |
| 500 points | 768 | <1s |
| 1000 points | 768 | ~2s |
| 5000 points | 768 | ~15s |

HDBSCAN scales O(n log n) in practice. For typical usage (100-1000 experiences), performance is excellent.

### Optimization Strategies

1. **Async retrieval**: VectorStore.scroll() is async, doesn't block
2. **Batch processing**: Could parallelize multi-axis clustering (future)
3. **Caching**: Cluster results could be cached until new experiences added
4. **Incremental updates**: Future optimization (requires tracking membership changes)

### Memory Usage

- **Embeddings**: 768 dims * 4 bytes/float * n_points
  - 1000 points = ~3 MB
- **HDBSCAN working memory**: ~5x embedding size
  - 1000 points = ~15 MB
- **Centroids**: Negligible (only k centroids, k << n)

Total: <50 MB for typical datasets.

## Alternatives Considered

### 1. K-Means Clustering

**Pros:**
- Fast (O(n) per iteration)
- Simple implementation
- Guaranteed to converge

**Cons:**
- Requires knowing k upfront (how many clusters?)
- Assumes spherical clusters
- Forces all points into clusters (no noise concept)
- Poor for semantic embeddings

**Decision:** HDBSCAN better fits semantic clustering needs.

### 2. DBSCAN (non-hierarchical)

**Pros:**
- Density-based (like HDBSCAN)
- Handles noise
- No cluster count required

**Cons:**
- Epsilon parameter hard to tune
- Single density threshold (HDBSCAN is multi-scale)
- HDBSCAN is strictly better for most use cases

**Decision:** HDBSCAN is the modern successor to DBSCAN.

### 3. Gaussian Mixture Models (GMM)

**Pros:**
- Probabilistic cluster assignment
- Soft clustering (membership probabilities)

**Cons:**
- Requires specifying component count
- Assumes Gaussian distributions
- More complex than needed

**Decision:** HDBSCAN provides probabilities too, without distribution assumptions.

### 4. Weighted HDBSCAN

Some libraries support weighted HDBSCAN where weights affect clustering itself, not just centroids.

**Pros:**
- Quality signal influences cluster formation

**Cons:**
- Not in scikit-learn HDBSCAN
- More complex implementation
- Unclear if quality should affect density (may bias toward gold-only clusters)

**Decision:** Use weights only for centroids. Let natural density drive clustering.

## Dependencies

Add to `pyproject.toml`:

```toml
dependencies = [
    # ... existing ...
    "hdbscan",       # Standalone HDBSCAN package
    "numpy>=1.24.0",
]
```

**Note:** HDBSCAN is a standalone package (`hdbscan`), not part of scikit-learn. Import with `import hdbscan`, NOT `from sklearn.cluster import HDBSCAN`.

## Logging Strategy

Use structured logging with `structlog`:

```python
import structlog

logger = structlog.get_logger(__name__)

# Log clustering results
logger.info(
    "clustering.complete",
    axis=axis,
    n_clusters=len(clusters),
    total_points=len(embeddings),
    noise_count=cluster_result.noise_count,
)

# Log performance
logger.debug(
    "clustering.performance",
    axis=axis,
    points=len(embeddings),
    duration_ms=duration,
)

# Log errors
logger.error(
    "clustering.failed",
    axis=axis,
    error=str(e),
)
```

## Open Questions

1. **Cluster persistence:** Should cluster assignments be stored in VectorStore payload?
   - **Recommendation:** Not in v1. Clustering is computed on-demand. Future: cache results.

2. **Parameter tuning UI:** How should users adjust HDBSCAN parameters?
   - **Recommendation:** Start with sensible defaults. Add config file if needed. No UI in v1.

3. **Cluster stability:** How to detect when clusters change significantly?
   - **Recommendation:** Out of scope for v1. Could add cluster similarity metrics later.

4. **Cross-axis patterns:** Should we analyze correlations between axes?
   - **Recommendation:** Future work. Independent clustering is simpler and sufficient for value formation.

## Success Criteria

Implementation is complete when:

1. ✅ All acceptance criteria from spec are met
2. ✅ Test coverage ≥ 90% for clustering module
3. ✅ All tests pass in isolation and in suite
4. ✅ Code passes `ruff` linting
5. ✅ Code passes `mypy --strict` type checking
6. ✅ Docstrings present for all public APIs
7. ✅ Integration test with real Qdrant passes
8. ✅ Performance targets met (500 points in <1s)
9. ✅ Manual testing: Can cluster synthetic experiences successfully

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Too many noise points | Poor cluster quality | Medium | Tune min_samples down to 2 |
| HDBSCAN too slow | User frustration | Low | Batch process, add caching |
| Weights don't affect clustering | Misleading centroids | Low | Document weight semantics clearly |
| Empty axis collections | Runtime errors | Medium | Raise clear ValueError, skip in cluster_all |
| Cluster count instability | Inconsistent values | Medium | Use "eom" method, conservative parameters |

## Conclusion

This proposal implements density-based clustering with weighted centroids, providing:

- **Automatic pattern discovery** via HDBSCAN (no manual cluster count)
- **Quality-aware centroids** weighted by confidence tiers
- **Multi-axis clustering** for comprehensive experience analysis
- **Noise handling** to exclude outliers gracefully
- **Scalable performance** for 100-1000 experiences per axis

The design prioritizes **simplicity** (sensible defaults, clear errors) and **correctness** (weighted centroids, noise exclusion) over advanced features. This provides a solid foundation for value formation while keeping the implementation maintainable and testable.
