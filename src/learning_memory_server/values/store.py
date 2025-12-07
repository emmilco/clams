"""ValueStore implementation."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import numpy as np

from learning_memory_server.embedding.base import EmbeddingService
from learning_memory_server.storage.base import VectorStore

from .types import ClusterInfo, Experience, ValidationResult, Value

if TYPE_CHECKING:
    from learning_memory_server.clustering import ExperienceClusterer

# Valid clustering axes (domain is NOT an axis - it's a metadata filter)
VALID_AXES = {"full", "strategy", "surprise", "root_cause"}

# Collection names (aligned with SPEC-002-14 ghap_* naming)
EXPERIENCES_COLLECTION_PREFIX = "ghap_"  # e.g., "ghap_full"
VALUES_COLLECTION = "values"


def cosine_distance(a: np.ndarray[Any, Any], b: np.ndarray[Any, Any]) -> float:
    """Calculate cosine distance between two vectors.

    Args:
        a: First vector
        b: Second vector

    Returns:
        Cosine distance (1 - cosine_similarity)
    """
    return float(1.0 - np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


class ValueStore:
    """Validates and stores agent-generated values."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        clusterer: "ExperienceClusterer",
    ) -> None:
        """Initialize ValueStore.

        Args:
            embedding_service: Service for embedding value candidates
            vector_store: Storage for validated values
            clusterer: ExperienceClusterer for retrieving cluster data
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
            ValueError: If axis is invalid or insufficient data for clustering
        """
        if axis not in VALID_AXES:
            raise ValueError(f"Invalid axis '{axis}'. Must be one of: {VALID_AXES}")

        # Delegate to ExperienceClusterer (returns clustering.ClusterInfo)
        from learning_memory_server.clustering.types import (
            ClusterInfo as ClusteringClusterInfo,
        )

        try:
            clustering_results: list[
                ClusteringClusterInfo
            ] = await self.clusterer.cluster_axis(axis)
        except ValueError as e:
            # Re-raise with context about insufficient data
            raise ValueError(f"Cannot get clusters for axis '{axis}': {e}") from e

        # Convert to values.ClusterInfo and add cluster_id
        cluster_result = [
            ClusterInfo(
                cluster_id=f"{axis}_{c.label}",
                axis=axis,
                label=c.label,
                centroid=c.centroid,
                member_ids=c.member_ids,
                size=c.size,
                avg_weight=c.avg_weight,
            )
            for c in clustering_results
        ]

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
            int(label_str)  # Validate label is an integer
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
                collection=collection, id=member_id, with_vector=True
            )

            if result is not None and result.vector is not None:
                # Extract weight from payload (confidence tier)
                weight = result.payload.get("confidence_weight", 1.0)

                experiences.append(
                    Experience(
                        id=result.id,
                        embedding=result.vector,
                        payload=result.payload,
                        weight=weight,
                    )
                )

        return experiences

    async def validate_value_candidate(
        self, text: str, cluster_id: str
    ) -> ValidationResult:
        """Validate a value candidate against a cluster.

        Args:
            text: Candidate value text
            cluster_id: Target cluster identifier

        Returns:
            ValidationResult with validity and metrics
        """
        # Get cluster and members
        try:
            cluster = await self._get_cluster(cluster_id)
            members = await self.get_cluster_members(cluster_id)
        except ValueError as e:
            # Return validation failure instead of raising exception
            return ValidationResult(valid=False, reason=str(e))

        if len(members) == 0:
            return ValidationResult(valid=False, reason="Cluster has no members")

        # Embed candidate
        candidate_embedding = await self.embedding_service.embed(text)

        # Calculate distances
        candidate_dist = cosine_distance(candidate_embedding, cluster.centroid)
        member_dists = [
            cosine_distance(m.embedding, cluster.centroid) for m in members
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
                threshold=threshold,
            )
        else:
            return ValidationResult(
                valid=False,
                reason=(
                    f"Value too far from centroid "
                    f"(distance={candidate_dist:.3f}, "
                    f"threshold={threshold:.3f} "
                    f"[mean={mean_dist:.3f} + 0.5*std={std_dist:.3f}])"
                ),
                candidate_distance=candidate_dist,
                mean_distance=mean_dist,
                std_distance=std_dist,
                threshold=threshold,
            )

    async def store_value(self, text: str, cluster_id: str, axis: str) -> Value:
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
        timestamp = datetime.now(UTC).isoformat()
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
                "similarity": validation.similarity,
            },
        }

        # Store in values collection
        await self.vector_store.upsert(
            collection=VALUES_COLLECTION,
            id=value_id,
            vector=embedding,
            payload=payload,
        )

        # Return Value object
        validation_metadata: dict[str, Any] = payload["validation"]  # type: ignore[assignment]
        return Value(
            id=value_id,
            text=text,
            cluster_id=cluster_id,
            axis=axis,
            embedding=embedding,
            cluster_size=cluster.size,
            created_at=timestamp,
            metadata=validation_metadata,
        )

    async def list_values(self, axis: str | None = None) -> list[Value]:
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
            with_vectors=True,
        )

        # Convert to Value objects
        values = []
        for result in results:
            if result.vector is not None:
                values.append(
                    Value(
                        id=result.id,
                        text=result.payload["text"],
                        cluster_id=result.payload["cluster_id"],
                        axis=result.payload["axis"],
                        embedding=result.vector,
                        cluster_size=result.payload["cluster_size"],
                        created_at=result.payload["created_at"],
                        metadata=result.payload.get("validation", {}),
                    )
                )

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
