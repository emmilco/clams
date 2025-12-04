# SPEC-002-13: ValueStore Validation and Storage

## Overview

The ValueStore validates and stores agent-generated values from clustered experiences. It provides the server-side infrastructure for the agent-driven value formation workflow.

## Purpose

Value formation is **agent-driven**, not server-driven. The server provides:
1. Clustering of experiences on multiple axes
2. Access to cluster members for agent inspection
3. Validation of agent-generated value candidates
4. Storage of validated values with embeddings

The Claude Code agent (via a slash command like `/retro`) reads cluster data, generates value text, validates it, and stores it back to the server.

## Dependencies

- `EmbeddingService`: Embed value candidates for validation and storage
- `VectorStore`: Store validated values in the `values` collection
- `Clusterer`: Provide cluster centroids and member data (from SPEC-002-12)

## Interface

```python
from dataclasses import dataclass
from typing import List, Optional
import numpy as np
from learning_memory_server.embedding.base import EmbeddingService, Vector
from learning_memory_server.storage.base import VectorStore


@dataclass
class ValidationResult:
    """Result of validating a value candidate against a cluster."""

    valid: bool
    similarity: Optional[float] = None  # 1 - cosine_distance if valid
    reason: Optional[str] = None  # Explanation if invalid
    candidate_distance: Optional[float] = None  # Distance to centroid
    mean_distance: Optional[float] = None  # Mean member distance
    std_distance: Optional[float] = None  # Std dev of member distances
    threshold: Optional[float] = None  # mean + 0.5*std (validation threshold)


@dataclass
class Value:
    """A stored value derived from a cluster of experiences."""

    id: str  # Format: "value_{axis}_{cluster_label}_{timestamp}"
    text: str
    cluster_id: str
    axis: str  # One of 4 clustering axes: "full", "strategy", "surprise", "root_cause"
              # Note: "domain" is NOT an axis - it's a metadata filter on experiences
    embedding: Vector
    cluster_size: int
    created_at: str  # ISO 8601 timestamp
    metadata: dict  # Additional info (cluster label, validation metrics, etc.)


@dataclass
class ClusterInfo:
    """Information about a cluster (from Clusterer)."""

    cluster_id: str  # Unique identifier
    axis: str
    label: int  # HDBSCAN cluster label
    centroid: Vector
    member_ids: List[str]
    size: int
    avg_weight: float  # Average confidence weight of members


@dataclass
class Experience:
    """A single experience from a cluster."""

    id: str
    embedding: Vector
    payload: dict  # Contains full GHAP data
    weight: float  # Confidence tier weight


class ValueStore:
    """Validates and stores agent-generated values."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        clusterer: "Clusterer"  # From SPEC-002-12
    ) -> None:
        """Initialize ValueStore.

        Args:
            embedding_service: Service for embedding value candidates
            vector_store: Storage for validated values
            clusterer: Clusterer for retrieving cluster data
        """
        ...

    async def get_clusters(self, axis: str) -> List[ClusterInfo]:
        """Get all clusters for a given axis.

        Args:
            axis: Clustering axis ("full", "strategy", "surprise", "root_cause")

        Returns:
            List of ClusterInfo objects sorted by size (descending)

        Raises:
            ValueError: If axis is invalid
        """
        ...

    async def get_cluster_members(self, cluster_id: str) -> List[Experience]:
        """Get all experiences in a cluster.

        Args:
            cluster_id: Cluster identifier

        Returns:
            List of Experience objects with embeddings and payloads

        Raises:
            ValueError: If cluster_id is invalid or not found
        """
        ...

    async def validate_value_candidate(
        self,
        text: str,
        cluster_id: str
    ) -> ValidationResult:
        """Validate a value candidate against a cluster.

        Validation logic: The candidate embedding must be within 1 standard
        deviation of the mean member distance to the centroid. This stricter
        threshold ensures values are semantically central to the cluster.

        Args:
            text: Candidate value text
            cluster_id: Target cluster identifier

        Returns:
            ValidationResult with validity and metrics

        Raises:
            ValueError: If cluster_id is invalid
        """
        ...

    async def store_value(
        self,
        text: str,
        cluster_id: str,
        axis: str
    ) -> Value:
        """Store a validated value.

        This method embeds the text and stores it in the values collection.
        It does NOT re-validate; the agent should call validate_value_candidate
        first. However, for safety, this method will raise if the value would
        fail validation.

        Args:
            text: Value text
            cluster_id: Source cluster identifier
            axis: Clustering axis

        Returns:
            The stored Value object

        Raises:
            ValueError: If cluster_id is invalid or value fails validation
        """
        ...

    async def list_values(self, axis: Optional[str] = None) -> List[Value]:
        """List all stored values, optionally filtered by axis.

        Args:
            axis: Optional axis filter

        Returns:
            List of Value objects sorted by created_at (descending)
        """
        ...
```

## Validation Logic

The centroid distance validation ensures values are semantically central to the cluster:

```python
async def validate_value_candidate(
    self,
    text: str,
    cluster_id: str
) -> ValidationResult:
    # Embed candidate
    candidate_embedding = await self.embedding_service.embed(text)

    # Get cluster info and members
    cluster = await self._get_cluster(cluster_id)
    members = await self.get_cluster_members(cluster_id)

    # Calculate distances
    candidate_dist = cosine_distance(candidate_embedding, cluster.centroid)
    member_dists = [
        cosine_distance(m.embedding, cluster.centroid)
        for m in members
    ]
    mean_dist = np.mean(member_dists)
    std_dist = np.std(member_dists)
    threshold = mean_dist + 0.5 * std_dist  # 0.5 standard deviation (conservative)

    # Validate: candidate must be within 0.5 std dev of mean
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
```

## Agent-Driven Value Formation Flow

The typical workflow (triggered by user via `/retro` command):

1. **Agent calls** `get_clusters(axis)` to see available clusters
2. **Agent selects** a cluster to explore (e.g., largest cluster on "full" axis)
3. **Agent calls** `get_cluster_members(cluster_id)` to read experiences
4. **Agent analyzes** the experiences and generates a candidate value statement
5. **Agent calls** `validate_value_candidate(text, cluster_id)`
6. **If valid**: Agent calls `store_value(text, cluster_id, axis)`
7. **If invalid**: Agent revises the value text and retries validation

The server never generates value text. The agent owns the value formation process.

## Storage

Values are stored in the `values` collection in VectorStore with the following payload:

```python
{
    "text": str,           # Value statement
    "cluster_id": str,     # Source cluster
    "axis": str,           # Clustering axis
    "cluster_label": int,  # HDBSCAN label
    "cluster_size": int,   # Number of members
    "created_at": str,     # ISO 8601 timestamp
    "validation": {
        "candidate_distance": float,
        "mean_distance": float,
        "similarity": float
    }
}
```

## Error Handling

- `ValueError`: Invalid axis, cluster_id, or validation failure
- `RuntimeError`: Database not initialized, embedding service unavailable
- All async errors propagate to the caller (agent/MCP server)

## Acceptance Criteria

1. **Cluster Access**
   - `get_clusters(axis)` returns clusters sorted by size (descending)
   - `get_cluster_members(cluster_id)` returns experiences with embeddings
   - Invalid axis or cluster_id raises `ValueError`

2. **Validation**
   - `validate_value_candidate(text, cluster_id)` correctly implements 0.5-std-dev threshold validation
   - Valid candidates (distance <= mean + 0.5*std) return `ValidationResult` with `valid=True`
   - Invalid candidates return `ValidationResult` with `valid=False` and explanation including threshold

3. **Storage**
   - `store_value(text, cluster_id, axis)` embeds and stores values in `values` collection
   - Stored values include all required metadata (cluster_id, axis, validation metrics)
   - `list_values(axis)` filters correctly and returns values sorted by recency

4. **Testing**
   - Unit tests with mock embedding service and in-memory vector store
   - Integration tests with real Clusterer (SPEC-002-12)
   - Test cases:
     - Valid value candidate (distance <= mean + 0.5*std)
     - Invalid value candidate (distance > mean + 0.5*std)
     - Multiple values per cluster
     - Filtering by axis
     - Edge cases: empty clusters, single-member clusters, very tight clusters (low std)

5. **Type Safety**
   - All public methods have full type hints
   - mypy strict mode passes
   - Dataclasses use proper types (Vector = np.ndarray, etc.)

6. **Async Compliance**
   - All I/O methods are async
   - No blocking calls in async context
   - Tests use pytest-asyncio
