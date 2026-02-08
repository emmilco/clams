"""Type definitions for value storage."""

from dataclasses import dataclass, field
from typing import Any

from calm.embedding.base import Vector


@dataclass
class ValidationResult:
    """Result of validating a value candidate against a cluster."""

    valid: bool
    similarity: float | None = None
    reason: str | None = None
    candidate_distance: float | None = None
    mean_distance: float | None = None
    std_distance: float | None = None
    threshold: float | None = None


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
    metadata: dict[str, Any] = field(default_factory=dict)


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
    payload: dict[str, Any]
    weight: float
