"""Types for clustering module."""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


@dataclass
class ClusterResult:
    """Result from clustering operation."""

    labels: npt.NDArray[np.int64]  # Cluster labels (same length as input)
    n_clusters: int  # Number of clusters found
    noise_count: int  # Number of points labeled as noise (-1)
    probabilities: npt.NDArray[np.float64]  # Cluster membership probabilities


@dataclass
class ClusterInfo:
    """Information about a single cluster."""

    label: int  # Cluster label (0, 1, 2, ...)
    centroid: npt.NDArray[np.float32]  # Weighted centroid vector
    member_ids: list[str]  # IDs of members in this cluster
    size: int  # Number of members
    avg_weight: float  # Average weight of members


# Confidence tier weight mappings
CONFIDENCE_WEIGHTS = {
    "gold": 1.0,
    "silver": 0.8,
    "bronze": 0.5,
    "abandoned": 0.2,
}


def get_weight(tier: str | None) -> float:
    """Get weight for confidence tier.

    Args:
        tier: Confidence tier string or None

    Returns:
        Weight value (0.2-1.0), defaults to 0.5 (bronze) for None/invalid
    """
    if tier is None:
        return 0.5  # Default to bronze weight
    return CONFIDENCE_WEIGHTS.get(tier.lower(), 0.5)  # Default: bronze
