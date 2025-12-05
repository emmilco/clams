"""Experience clustering along multiple semantic axes."""

import numpy as np
import structlog

from ..storage.base import VectorStore
from .clusterer import Clusterer
from .types import ClusterInfo, get_weight

logger = structlog.get_logger(__name__)

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
        """Initialize with VectorStore and Clusterer.

        Args:
            vector_store: VectorStore instance with indexed experiences
            clusterer: Clusterer instance with HDBSCAN configuration
        """
        self.vector_store = vector_store
        self.clusterer = clusterer

    async def count_experiences(self, axis: str) -> int:
        """Count experiences for a given axis.

        Args:
            axis: Axis name (full, strategy, surprise, root_cause)

        Returns:
            Number of experiences indexed for this axis

        Raises:
            ValueError: If axis is invalid
        """
        if axis not in AXIS_COLLECTIONS:
            raise ValueError(
                f"Invalid axis: {axis}. Valid axes: {list(AXIS_COLLECTIONS.keys())}"
            )

        collection = AXIS_COLLECTIONS[axis]
        results = await self.vector_store.scroll(
            collection=collection,
            limit=10000,
            with_vectors=False,
        )
        return len(results)

    async def cluster_axis(self, axis: str) -> list[ClusterInfo]:
        """Cluster experiences along a single axis.

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

        Raises:
            ValueError: If axis is invalid
            ValueError: If no embeddings found for axis (collection empty)
        """
        if axis not in AXIS_COLLECTIONS:
            raise ValueError(
                f"Invalid axis: {axis}. Valid axes: {list(AXIS_COLLECTIONS.keys())}"
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
            logger.warning(
                "clustering.scroll_limit_reached",
                axis=axis,
                collection=collection,
                count=10000,
                message="May have truncated results - consider pagination",
            )

        if not results:
            raise ValueError(
                f"No embeddings found for axis '{axis}' (collection: {collection})"
            )

        # Extract data from results
        embeddings = np.array([r.vector for r in results], dtype=np.float32)
        ids = [r.id for r in results]
        tiers = [
            str(r.payload.get("confidence_tier", "bronze")) for r in results
        ]
        weights = np.array([get_weight(tier) for tier in tiers], dtype=np.float32)

        # Cluster
        cluster_result = self.clusterer.cluster(embeddings, weights)

        # Check for all-noise result (no clusters found)
        if cluster_result.n_clusters == 0:
            logger.warning(
                "clustering.all_noise",
                axis=axis,
                total_points=len(embeddings),
                noise_count=cluster_result.noise_count,
                message="HDBSCAN labeled all points as noise - no clusters found",
            )
            return []  # Return empty list if no clusters

        # Compute centroids
        clusters = self.clusterer.compute_centroids(
            embeddings=embeddings,
            labels=cluster_result.labels,
            ids=ids,
            weights=weights,
        )

        logger.info(
            "clustering.complete",
            axis=axis,
            n_clusters=len(clusters),
            total_points=len(embeddings),
            noise_count=cluster_result.noise_count,
        )

        return clusters

    async def cluster_all_axes(self) -> dict[str, list[ClusterInfo]]:
        """Cluster experiences on all axes.

        Returns:
            Dict mapping axis name to list of ClusterInfo
            Example: {"full": [...], "strategy": [...], "surprise": [...]}

        Notes:
            - Axes with no data are omitted from result (not empty lists)
            - Each axis clustered independently with same parameters
        """
        results = {}
        for axis in AXIS_COLLECTIONS.keys():
            try:
                results[axis] = await self.cluster_axis(axis)
            except ValueError as e:
                # Skip axes with no data
                # Log warning but don't fail entire operation
                logger.warning(
                    "clustering.axis_skipped",
                    axis=axis,
                    error=str(e),
                    message="Skipping axis due to error",
                )
                continue

        return results
