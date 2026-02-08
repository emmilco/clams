"""ValueStore implementation."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import numpy as np

from calm.embedding.base import EmbeddingService
from calm.storage.base import VectorStore
from calm.tools.learning import VALID_AXES

from .types import ClusterInfo, Experience, ValidationResult, Value

if TYPE_CHECKING:
    from calm.clustering import ExperienceClusterer

EXPERIENCES_COLLECTION_PREFIX = "ghap_"
VALUES_COLLECTION = "values"


def cosine_distance(a: np.ndarray[Any, Any], b: np.ndarray[Any, Any]) -> float:
    """Calculate cosine distance between two vectors."""
    return float(1.0 - np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


class ValueStore:
    """Validates and stores agent-generated values."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        clusterer: "ExperienceClusterer",
    ) -> None:
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.clusterer = clusterer
        self._collection_ensured = False

    async def _ensure_values_collection(self) -> None:
        if self._collection_ensured:
            return

        try:
            await self.vector_store.create_collection(
                name=VALUES_COLLECTION,
                dimension=self.embedding_service.dimension,
                distance="cosine",
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "already exists" in error_msg or "409" in str(e):
                pass
            else:
                raise

        self._collection_ensured = True

    async def get_clusters(self, axis: str) -> list[ClusterInfo]:
        if axis not in VALID_AXES:
            raise ValueError(f"Invalid axis '{axis}'. Must be one of: {VALID_AXES}")

        experience_count = await self.clusterer.count_experiences(axis)
        if experience_count < 20:
            raise ValueError(
                f"Not enough experiences for clustering. "
                f"Found {experience_count}, need at least 20."
            )

        from calm.clustering.types import (
            ClusterInfo as ClusteringClusterInfo,
        )

        try:
            clustering_results: list[
                ClusteringClusterInfo
            ] = await self.clusterer.cluster_axis(axis)
        except ValueError as e:
            raise ValueError(f"Cannot get clusters for axis '{axis}': {e}") from e

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

        cluster_result.sort(key=lambda c: c.size, reverse=True)

        return cluster_result

    async def get_cluster_members(self, cluster_id: str) -> list[Experience]:
        try:
            axis, label_str = cluster_id.rsplit("_", 1)
            int(label_str)
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid cluster_id format: {cluster_id}")

        if axis not in VALID_AXES:
            raise ValueError(f"Invalid axis in cluster_id: {axis}")

        clusters = await self.get_clusters(axis)
        cluster = next((c for c in clusters if c.cluster_id == cluster_id), None)

        if cluster is None:
            raise ValueError(f"Cluster not found: {cluster_id}")

        collection = f"{EXPERIENCES_COLLECTION_PREFIX}{axis}"
        experiences = []

        for member_id in cluster.member_ids:
            result = await self.vector_store.get(
                collection=collection, id=member_id, with_vector=True
            )

            if result is not None and result.vector is not None:
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
        try:
            cluster = await self._get_cluster(cluster_id)
            members = await self.get_cluster_members(cluster_id)
        except ValueError as e:
            if "Not enough experiences" in str(e):
                return ValidationResult(
                    valid=False,
                    reason=str(e),
                )
            return ValidationResult(valid=False, reason=str(e))

        if len(members) == 0:
            return ValidationResult(valid=False, reason="Cluster has no members")

        candidate_embedding = await self.embedding_service.embed(text)

        candidate_dist = cosine_distance(candidate_embedding, cluster.centroid)
        member_dists = [
            cosine_distance(m.embedding, cluster.centroid) for m in members
        ]
        mean_dist = float(np.mean(member_dists))
        std_dist = float(np.std(member_dists))
        threshold = mean_dist + 0.5 * std_dist

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
        await self._ensure_values_collection()

        validation = await self.validate_value_candidate(text, cluster_id)
        if not validation.valid:
            raise ValueError(f"Value failed validation: {validation.reason}")

        cluster = await self._get_cluster(cluster_id)

        embedding = await self.embedding_service.embed(text)

        timestamp = datetime.now(UTC).isoformat()
        value_id = f"value_{axis}_{cluster.label}_{uuid.uuid4().hex[:8]}"

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

        await self.vector_store.upsert(
            collection=VALUES_COLLECTION,
            id=value_id,
            vector=embedding,
            payload=payload,
        )

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
        await self._ensure_values_collection()

        filters = {}
        if axis is not None:
            if axis not in VALID_AXES:
                raise ValueError(f"Invalid axis: {axis}")
            filters["axis"] = axis

        results = await self.vector_store.scroll(
            collection=VALUES_COLLECTION,
            limit=1000,
            filters=filters if filters else None,
            with_vectors=True,
        )

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

        values.sort(key=lambda v: v.created_at, reverse=True)

        return values

    async def _get_cluster(self, cluster_id: str) -> ClusterInfo:
        try:
            axis, _ = cluster_id.rsplit("_", 1)
        except ValueError:
            raise ValueError(f"Invalid cluster_id format: {cluster_id}")

        clusters = await self.get_clusters(axis)
        cluster = next((c for c in clusters if c.cluster_id == cluster_id), None)

        if cluster is None:
            raise ValueError(f"Cluster not found: {cluster_id}")

        return cluster
