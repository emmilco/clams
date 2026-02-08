"""Experience clustering along multiple semantic axes."""

import numpy as np
import structlog

from calm.storage.base import VectorStore

from .clusterer import Clusterer
from .types import ClusterInfo, get_weight

logger = structlog.get_logger(__name__)

AXIS_COLLECTIONS = {
    "full": "ghap_full",
    "strategy": "ghap_strategy",
    "surprise": "ghap_surprise",
    "root_cause": "ghap_root_cause",
}


class ExperienceClusterer:
    """Cluster experiences along multiple semantic axes."""

    def __init__(self, vector_store: VectorStore, clusterer: Clusterer):
        self.vector_store = vector_store
        self.clusterer = clusterer

    async def count_experiences(self, axis: str) -> int:
        if axis not in AXIS_COLLECTIONS:
            raise ValueError(
                f"Invalid axis: {axis}. Valid axes: {list(AXIS_COLLECTIONS.keys())}"
            )

        collection = AXIS_COLLECTIONS[axis]
        try:
            results = await self.vector_store.scroll(
                collection=collection,
                limit=10000,
                with_vectors=False,
            )
            return len(results)
        except Exception as e:
            if "not found" in str(e).lower() or "404" in str(e):
                return 0
            raise

    async def cluster_axis(self, axis: str) -> list[ClusterInfo]:
        if axis not in AXIS_COLLECTIONS:
            raise ValueError(
                f"Invalid axis: {axis}. Valid axes: {list(AXIS_COLLECTIONS.keys())}"
            )

        collection = AXIS_COLLECTIONS[axis]

        try:
            results = await self.vector_store.scroll(
                collection=collection,
                limit=10000,
                with_vectors=True,
            )
        except Exception as e:
            if "not found" in str(e).lower() or "404" in str(e):
                raise ValueError(
                    f"No embeddings found for axis '{axis}' (collection: {collection})"
                )
            raise

        if len(results) == 10000:
            logger.warning(
                "clustering.scroll_limit_reached",
                axis=axis,
                collection=collection,
                count=10000,
            )

        if not results:
            raise ValueError(
                f"No embeddings found for axis '{axis}' (collection: {collection})"
            )

        embeddings = np.array([r.vector for r in results], dtype=np.float32)
        ids = [r.id for r in results]
        tiers = [
            str(r.payload.get("confidence_tier", "bronze")) for r in results
        ]
        weights = np.array([get_weight(tier) for tier in tiers], dtype=np.float32)

        cluster_result = self.clusterer.cluster(embeddings, weights)

        if cluster_result.n_clusters == 0:
            logger.warning(
                "clustering.all_noise",
                axis=axis,
                total_points=len(embeddings),
                noise_count=cluster_result.noise_count,
            )
            return []

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
        results = {}
        for axis in AXIS_COLLECTIONS.keys():
            try:
                results[axis] = await self.cluster_axis(axis)
            except ValueError as e:
                logger.warning(
                    "clustering.axis_skipped",
                    axis=axis,
                    error=str(e),
                )
                continue

        return results
