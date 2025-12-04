"""HDBSCAN clustering with weighted centroids."""

import hdbscan
import numpy as np
import numpy.typing as npt

from .types import ClusterInfo, ClusterResult


class Clusterer:
    """HDBSCAN clustering with weighted centroids."""

    def __init__(
        self,
        min_cluster_size: int = 5,
        min_samples: int = 3,
        metric: str = "cosine",
        cluster_selection_method: str = "eom",
    ):
        """Initialize clusterer with HDBSCAN parameters.

        Args:
            min_cluster_size: Minimum size of a cluster (default: 5)
            min_samples: Conservative parameter for core points (default: 3)
            metric: Distance metric (default: "cosine")
            cluster_selection_method: "eom" (Excess of Mass) or "leaf"
        """
        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples
        self.metric = metric
        self.cluster_selection_method = cluster_selection_method

    def cluster(
        self,
        embeddings: npt.NDArray[np.float32],
        weights: npt.NDArray[np.float32] | None = None,
    ) -> ClusterResult:
        """Cluster embeddings using HDBSCAN.

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
        # For cosine metric, we need to normalize embeddings first
        # Using euclidean on normalized vectors is equivalent to cosine distance
        if self.metric == "cosine":
            # Normalize embeddings for cosine similarity
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1  # Avoid division by zero
            normalized_embeddings = embeddings / norms

            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=self.min_cluster_size,
                min_samples=self.min_samples,
                metric="euclidean",  # Use euclidean on normalized vectors
                cluster_selection_method=self.cluster_selection_method,
            )
            labels = clusterer.fit_predict(normalized_embeddings)
        else:
            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=self.min_cluster_size,
                min_samples=self.min_samples,
                metric=self.metric,
                cluster_selection_method=self.cluster_selection_method,
            )
            labels = clusterer.fit_predict(embeddings)

        probabilities = clusterer.probabilities_

        # Count clusters (excluding noise = -1)
        unique_labels = set(labels)
        unique_labels.discard(-1)  # Remove noise label
        n_clusters = len(unique_labels)

        # Count noise points
        noise_count = int(np.sum(labels == -1))

        return ClusterResult(
            labels=labels,
            n_clusters=n_clusters,
            noise_count=noise_count,
            probabilities=probabilities,
        )

    def compute_centroids(
        self,
        embeddings: npt.NDArray[np.float32],
        labels: npt.NDArray[np.int64],
        ids: list[str],
        weights: npt.NDArray[np.float32] | None = None,
    ) -> list[ClusterInfo]:
        """Compute weighted centroids for each cluster.

        Args:
            embeddings: Array of shape (n_samples, n_dimensions)
                        These should be the ORIGINAL embeddings (not normalized).
                        When cosine metric is used, cluster() normalizes internally
                        but returns labels computed on normalized space.
                        Centroids are then computed on original embeddings.
            labels: Cluster labels from HDBSCAN (-1 = noise)
            ids: IDs corresponding to each embedding
            weights: Optional weights for weighted centroid computation

        Returns:
            List of ClusterInfo, one per cluster (excluding noise)
            Sorted by cluster label (0, 1, 2, ...)

        Raises:
            ValueError: If array shapes don't match
            ValueError: If any cluster has zero total weight

        Note:
            When cosine metric is used, clustering is performed on normalized
            embeddings (cosine distance), but centroids are computed from
            original embeddings. This is intentional: centroids represent
            the weighted mean in the original embedding space, not the
            normalized space.
        """
        if len(embeddings) != len(labels) or len(embeddings) != len(ids):
            raise ValueError(
                f"Array lengths don't match: embeddings={len(embeddings)}, "
                f"labels={len(labels)}, ids={len(ids)}"
            )

        weights_array: npt.NDArray[np.float32]
        if weights is None:
            weights_array = np.ones(len(embeddings), dtype=np.float32)
        else:
            weights_array = weights

        if len(weights_array) != len(embeddings):
            raise ValueError(
                f"Weights length ({len(weights_array)}) doesn't match "
                f"embeddings ({len(embeddings)})"
            )

        # Get unique cluster labels (excluding noise = -1)
        unique_labels = sorted(set(labels.tolist()))
        if -1 in unique_labels:
            unique_labels.remove(-1)

        clusters = []
        for label in unique_labels:
            # Get members of this cluster
            mask = labels == label
            cluster_embeddings = embeddings[mask]
            cluster_weights = weights_array[mask]
            cluster_ids = [ids[i] for i in np.where(mask)[0]]

            # Compute weighted centroid
            weighted_sum = np.sum(
                cluster_embeddings * cluster_weights[:, np.newaxis], axis=0
            )
            weight_sum = np.sum(cluster_weights)

            # Validate non-zero weight sum (should never happen with valid inputs)
            if weight_sum == 0:
                raise ValueError(f"Cluster {label} has zero total weight")

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
