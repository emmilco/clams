"""Types for clustering module."""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


@dataclass
class ClusterResult:
    """Result from clustering operation."""

    labels: npt.NDArray[np.int64]
    n_clusters: int
    noise_count: int
    probabilities: npt.NDArray[np.float64]


@dataclass
class ClusterInfo:
    """Information about a single cluster."""

    label: int
    centroid: npt.NDArray[np.float32]
    member_ids: list[str]
    size: int
    avg_weight: float


CONFIDENCE_WEIGHTS = {
    "gold": 1.0,
    "silver": 0.8,
    "bronze": 0.5,
    "abandoned": 0.2,
}


def get_weight(tier: str | None) -> float:
    """Get weight for confidence tier."""
    if tier is None:
        return 0.5
    return CONFIDENCE_WEIGHTS.get(tier.lower(), 0.5)
