# SPEC-002-13: ValueStore - Technical Proposal

## Implementation Overview

The ValueStore will be implemented as a simple facade over existing infrastructure. It coordinates three components:
1. Clusterer (SPEC-002-12) - provides cluster data
2. EmbeddingService - embeds value candidates
3. VectorStore - stores validated values

The implementation is straightforward because the complex work (clustering, embedding, storage) is already handled by dependencies.

## File Structure

```
src/learning_memory_server/values/
├── __init__.py         # Export ValueStore and dataclasses
├── store.py            # ValueStore implementation
└── types.py            # ValidationResult, Value, ClusterInfo, Experience dataclasses

tests/values/
├── __init__.py
├── test_store.py       # Unit tests with mocks
└── test_integration.py # Integration tests with real Clusterer
```

## Module Design

### `types.py` - Dataclasses

```python
"""Type definitions for value storage."""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np

from learning_memory_server.embedding.base import Vector


@dataclass
class ValidationResult:
    """Result of validating a value candidate against a cluster."""

    valid: bool
    similarity: Optional[float] = None
    reason: Optional[str] = None
    candidate_distance: Optional[float] = None
    mean_distance: Optional[float] = None
    std_distance: Optional[float] = None
    threshold: Optional[float] = None  # mean + 1*std


@dataclass
class Value:
    """A stored value derived from a cluster of experiences."""

    id: str
    text: str
    cluster_id: str
    axis: str
    embedding: Vector
    cluster_size: int
    created_at: str
    metadata: dict = field(default_factory=dict)


@dataclass
class ClusterInfo:
    """Information about a cluster."""

    cluster_id: str
    axis: str
    label: int
    centroid: Vector
    member_ids: list[str]
    size: int
    avg_weight: float


@dataclass
class Experience:
    """A single experience from a cluster."""

    id: str
    embedding: Vector
    payload: dict
    weight: float
```

### `store.py` - Core Implementation

```python
"""ValueStore implementation."""

import uuid
from datetime import datetime
from typing import Optional

import numpy as np

from learning_memory_server.embedding.base import EmbeddingService
from learning_memory_server.storage.base import VectorStore

from .types import ClusterInfo, Experience, ValidationResult, Value


# Valid clustering axes (domain is NOT an axis - it's a metadata filter)
VALID_AXES = {"full", "strategy", "surprise", "root_cause"}

# Collection names (aligned with SPEC-001)
EXPERIENCES_COLLECTION_PREFIX = "experiences_"  # e.g., "experiences_full"
VALUES_COLLECTION = "values"


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate cosine distance between two vectors.

    Args:
        a: First vector
        b: Second vector

    Returns:
        Cosine distance (1 - cosine_similarity)
    """
    return 1.0 - np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


class ValueStore:
    """Validates and stores agent-generated values."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        clusterer: "Clusterer"  # Type hint for SPEC-002-12
    ) -> None:
        """Initialize ValueStore.

        Args:
            embedding_service: Service for embedding value candidates
            vector_store: Storage for validated values
            clusterer: Clusterer for retrieving cluster data
        """
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.clusterer = clusterer

    async def get_clusters(self, axis: str) -> list[ClusterInfo]:
        """Get all clusters for a given axis.

        Args:
            axis: Clustering axis

        Returns:
            List of ClusterInfo objects sorted by size (descending)

        Raises:
            ValueError: If axis is invalid
        """
        if axis not in VALID_AXES:
            raise ValueError(
                f"Invalid axis '{axis}'. Must be one of: {VALID_AXES}"
            )

        # Delegate to Clusterer
        cluster_result = await self.clusterer.cluster_axis(axis)

        # Sort by size descending
        cluster_result.sort(key=lambda c: c.size, reverse=True)

        return cluster_result

    async def get_cluster_members(self, cluster_id: str) -> list[Experience]:
        """Get all experiences in a cluster.

        Args:
            cluster_id: Cluster identifier

        Returns:
            List of Experience objects with embeddings and payloads

        Raises:
            ValueError: If cluster_id is invalid or not found
        """
        # Parse cluster_id: format is "{axis}_{label}"
        try:
            axis, label_str = cluster_id.rsplit("_", 1)
            label = int(label_str)
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid cluster_id format: {cluster_id}")

        if axis not in VALID_AXES:
            raise ValueError(f"Invalid axis in cluster_id: {axis}")

        # Get cluster info to find member IDs
        clusters = await self.get_clusters(axis)
        cluster = next((c for c in clusters if c.cluster_id == cluster_id), None)

        if cluster is None:
            raise ValueError(f"Cluster not found: {cluster_id}")

        # Fetch members from VectorStore
        collection = f"{EXPERIENCES_COLLECTION_PREFIX}{axis}"
        experiences = []

        for member_id in cluster.member_ids:
            result = await self.vector_store.get(
                collection=collection,
                id=member_id,
                with_vector=True
            )

            if result is not None:
                # Extract weight from payload (confidence tier)
                weight = result.payload.get("confidence_weight", 1.0)

                experiences.append(Experience(
                    id=result.id,
                    embedding=result.vector,
                    payload=result.payload,
                    weight=weight
                ))

        return experiences

    async def validate_value_candidate(
        self,
        text: str,
        cluster_id: str
    ) -> ValidationResult:
        """Validate a value candidate against a cluster.

        Args:
            text: Candidate value text
            cluster_id: Target cluster identifier

        Returns:
            ValidationResult with validity and metrics

        Raises:
            ValueError: If cluster_id is invalid
        """
        # Get cluster and members
        cluster = await self._get_cluster(cluster_id)
        members = await self.get_cluster_members(cluster_id)

        if len(members) == 0:
            return ValidationResult(
                valid=False,
                reason="Cluster has no members"
            )

        # Embed candidate
        candidate_embedding = await self.embedding_service.embed(text)

        # Calculate distances
        candidate_dist = cosine_distance(candidate_embedding, cluster.centroid)
        member_dists = [
            cosine_distance(m.embedding, cluster.centroid)
            for m in members
        ]
        mean_dist = float(np.mean(member_dists))
        std_dist = float(np.std(member_dists))
        threshold = mean_dist + 0.5 * std_dist  # 0.5 standard deviation (conservative)

        # Validate: candidate must be within 0.5 std dev of mean (strict)
        if candidate_dist <= threshold:
            return ValidationResult(
                valid=True,
                similarity=1.0 - candidate_dist,
                candidate_distance=candidate_dist,
                mean_distance=mean_dist,
                std_distance=std_dist,
                threshold=threshold
            )
        else:
            return ValidationResult(
                valid=False,
                reason=(
                    f"Value too far from centroid "
                    f"(distance={candidate_dist:.3f}, "
                    f"threshold={threshold:.3f} [mean={mean_dist:.3f} + 0.5*std={std_dist:.3f}])"
                ),
                candidate_distance=candidate_dist,
                mean_distance=mean_dist,
                std_distance=std_dist,
                threshold=threshold
            )

    async def store_value(
        self,
        text: str,
        cluster_id: str,
        axis: str
    ) -> Value:
        """Store a validated value.

        Args:
            text: Value text
            cluster_id: Source cluster identifier
            axis: Clustering axis

        Returns:
            The stored Value object

        Raises:
            ValueError: If cluster_id is invalid or value fails validation
        """
        # Validate first (safety check)
        validation = await self.validate_value_candidate(text, cluster_id)
        if not validation.valid:
            raise ValueError(f"Value failed validation: {validation.reason}")

        # Get cluster info
        cluster = await self._get_cluster(cluster_id)

        # Embed value
        embedding = await self.embedding_service.embed(text)

        # Generate ID
        timestamp = datetime.utcnow().isoformat()
        value_id = f"value_{axis}_{cluster.label}_{uuid.uuid4().hex[:8]}"

        # Prepare payload
        payload = {
            "text": text,
            "cluster_id": cluster_id,
            "axis": axis,
            "cluster_label": cluster.label,
            "cluster_size": cluster.size,
            "created_at": timestamp,
            "validation": {
                "candidate_distance": validation.candidate_distance,
                "mean_distance": validation.mean_distance,
                "threshold": validation.threshold,
                "similarity": validation.similarity
            }
        }

        # Store in values collection
        await self.vector_store.upsert(
            collection=VALUES_COLLECTION,
            id=value_id,
            vector=embedding,
            payload=payload
        )

        # Return Value object
        return Value(
            id=value_id,
            text=text,
            cluster_id=cluster_id,
            axis=axis,
            embedding=embedding,
            cluster_size=cluster.size,
            created_at=timestamp,
            metadata=payload["validation"]
        )

    async def list_values(self, axis: Optional[str] = None) -> list[Value]:
        """List all stored values, optionally filtered by axis.

        Args:
            axis: Optional axis filter

        Returns:
            List of Value objects sorted by created_at (descending)
        """
        # Build filters
        filters = {}
        if axis is not None:
            if axis not in VALID_AXES:
                raise ValueError(f"Invalid axis: {axis}")
            filters["axis"] = axis

        # Fetch from VectorStore
        results = await self.vector_store.scroll(
            collection=VALUES_COLLECTION,
            limit=1000,  # Reasonable upper bound
            filters=filters if filters else None,
            with_vectors=True
        )

        # Convert to Value objects
        values = []
        for result in results:
            values.append(Value(
                id=result.id,
                text=result.payload["text"],
                cluster_id=result.payload["cluster_id"],
                axis=result.payload["axis"],
                embedding=result.vector,
                cluster_size=result.payload["cluster_size"],
                created_at=result.payload["created_at"],
                metadata=result.payload.get("validation", {})
            ))

        # Sort by created_at descending
        values.sort(key=lambda v: v.created_at, reverse=True)

        return values

    async def _get_cluster(self, cluster_id: str) -> ClusterInfo:
        """Internal helper to get a single cluster by ID.

        Args:
            cluster_id: Cluster identifier

        Returns:
            ClusterInfo object

        Raises:
            ValueError: If cluster not found
        """
        # Parse axis from cluster_id
        try:
            axis, _ = cluster_id.rsplit("_", 1)
        except ValueError:
            raise ValueError(f"Invalid cluster_id format: {cluster_id}")

        clusters = await self.get_clusters(axis)
        cluster = next((c for c in clusters if c.cluster_id == cluster_id), None)

        if cluster is None:
            raise ValueError(f"Cluster not found: {cluster_id}")

        return cluster
```

## Testing Strategy

### Unit Tests (`test_store.py`)

Test with mock dependencies:

```python
import pytest
from unittest.mock import AsyncMock, Mock
import numpy as np

from learning_memory_server.values import ValueStore
from learning_memory_server.values.types import ClusterInfo, Experience


@pytest.fixture
def mock_embedding_service():
    service = AsyncMock()
    service.embed.return_value = np.array([0.5, 0.5], dtype=np.float32)
    return service


@pytest.fixture
def mock_vector_store():
    return AsyncMock()


@pytest.fixture
def mock_clusterer():
    clusterer = AsyncMock()
    # Mock cluster_axis to return test clusters
    clusterer.cluster_axis.return_value = [
        ClusterInfo(
            cluster_id="full_0",
            axis="full",
            label=0,
            centroid=np.array([1.0, 0.0], dtype=np.float32),
            member_ids=["exp_1", "exp_2", "exp_3"],
            size=3,
            avg_weight=0.9
        )
    ]
    return clusterer


@pytest.fixture
def value_store(mock_embedding_service, mock_vector_store, mock_clusterer):
    return ValueStore(mock_embedding_service, mock_vector_store, mock_clusterer)


class TestGetClusters:
    async def test_valid_axis(self, value_store):
        clusters = await value_store.get_clusters("full")
        assert len(clusters) > 0

    async def test_invalid_axis(self, value_store):
        with pytest.raises(ValueError, match="Invalid axis"):
            await value_store.get_clusters("invalid")


class TestValidation:
    async def test_valid_candidate(self, value_store, mock_embedding_service):
        # Mock embedding close to centroid
        mock_embedding_service.embed.return_value = np.array([0.95, 0.05])

        result = await value_store.validate_value_candidate(
            text="Test value",
            cluster_id="full_0"
        )

        assert result.valid is True
        assert result.similarity > 0

    async def test_invalid_candidate(self, value_store, mock_embedding_service):
        # Mock embedding far from centroid
        mock_embedding_service.embed.return_value = np.array([0.0, 1.0])

        result = await value_store.validate_value_candidate(
            text="Test value",
            cluster_id="full_0"
        )

        assert result.valid is False
        assert "too far from centroid" in result.reason
```

### Integration Tests (`test_integration.py`)

Test with real Clusterer (SPEC-002-12):

```python
import pytest

from learning_memory_server.embedding import MockEmbedding
from learning_memory_server.storage import InMemoryVectorStore
from learning_memory_server.clustering import Clusterer, ExperienceClusterer
from learning_memory_server.values import ValueStore


@pytest.fixture
async def integration_setup():
    """Set up real components for integration testing."""
    embedding_service = MockEmbedding()
    vector_store = InMemoryVectorStore()
    await vector_store.create_collection("experiences_full", 768)
    await vector_store.create_collection("values", 768)

    # Create real Clusterer
    clusterer = Clusterer(min_cluster_size=2, min_samples=1)
    experience_clusterer = ExperienceClusterer(vector_store, clusterer)

    # Create ValueStore
    value_store = ValueStore(embedding_service, vector_store, experience_clusterer)

    return value_store, vector_store


async def test_full_workflow(integration_setup):
    """Test complete value formation workflow."""
    value_store, vector_store = integration_setup

    # 1. Populate experiences
    # ... (insert test experiences)

    # 2. Get clusters
    clusters = await value_store.get_clusters("full")
    assert len(clusters) > 0

    # 3. Get members
    members = await value_store.get_cluster_members(clusters[0].cluster_id)
    assert len(members) > 0

    # 4. Validate candidate
    validation = await value_store.validate_value_candidate(
        text="Test principle",
        cluster_id=clusters[0].cluster_id
    )
    assert validation.valid is True

    # 5. Store value
    value = await value_store.store_value(
        text="Test principle",
        cluster_id=clusters[0].cluster_id,
        axis="full"
    )
    assert value.id is not None

    # 6. List values
    values = await value_store.list_values(axis="full")
    assert len(values) == 1
    assert values[0].text == "Test principle"
```

## Implementation Notes

### Async Compliance

All methods are async to comply with the codebase's async-native design:
- `embed()` is async (CPU-bound work in executor)
- VectorStore operations are async (I/O)
- Clusterer operations are async (computation + I/O)

### Error Handling

- `ValueError` for invalid inputs (axis, cluster_id)
- `RuntimeError` from dependencies propagates (database not initialized, etc.)
- Validation failures return `ValidationResult` with `valid=False` (not exceptions)
- `store_value()` validates before storing and raises `ValueError` if invalid

### Type Safety

- Full type hints on all public methods
- mypy strict mode compliance
- Proper use of `Vector` type alias from `embedding.base`
- Optional types for nullable fields

### Cluster ID Format

Cluster IDs are formatted as `{axis}_{label}` where:
- `axis` is the clustering axis (e.g., "full", "strategy", "surprise", "root_cause")
- `label` is the HDBSCAN cluster label (integer)

Example: `full_0`, `strategy_2`, `root_cause_1`

### Collection Names

Following SPEC-001 conventions:
- Experiences: `experiences_{axis}` (e.g., `experiences_full`, `experiences_strategy`)
- Values: `values` (single collection for all axes, filtered by payload)

## Dependencies on SPEC-002-12

The Clusterer (SPEC-002-12) must provide:
1. `cluster_axis(axis: str) -> List[ClusterInfo]` - Run clustering for an axis
2. ClusterInfo must include `cluster_id`, `centroid`, `member_ids`, `size`

The ValueStore delegates all clustering work to the Clusterer. It only adds:
- Embedding of value candidates
- Centroid distance validation
- Storage in the values collection

## Risk Assessment

**Low Risk**: This is a straightforward facade. The complexity lives in:
- Clusterer (SPEC-002-12) - handles clustering
- EmbeddingService (already implemented)
- VectorStore (already implemented)

The ValueStore just coordinates these pieces. The validation logic is simple math (cosine distance).

**Dependencies**: Blocked on SPEC-002-12 (Clusterer). Once that's complete, this task is trivial.

## Implementation Order

1. Create `types.py` with dataclasses
2. Create `store.py` with ValueStore implementation
3. Write unit tests with mocks
4. Write integration tests with real Clusterer (after SPEC-002-12)
5. Update `values/__init__.py` to export public API

## Acceptance Criteria Review

All criteria from spec.md are addressed:

1. **Cluster Access**: `get_clusters()` and `get_cluster_members()` implemented
2. **Validation**: Centroid distance logic implemented in `validate_value_candidate()`
3. **Storage**: `store_value()` and `list_values()` implemented with correct metadata
4. **Testing**: Comprehensive unit and integration test plan
5. **Type Safety**: Full type hints, mypy compliance
6. **Async Compliance**: All I/O methods are async

## Questions for Human Review

None. This is a straightforward implementation following established patterns. The design aligns with:
- SPEC-001 module specifications
- Existing async conventions
- Existing storage patterns (VectorStore, collections)
- Dependency on SPEC-002-12 (Clusterer)
