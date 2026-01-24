"""Embedding generators for validation testing.

This module generates embeddings with controlled cluster structure
for testing clustering algorithms with production-like data.

Reference: SPEC-034 Embedding Generator Design
Reference: BUG-031 - Clustering failed with diffuse data
"""

from typing import NamedTuple

import numpy as np
import numpy.typing as npt

from tests.fixtures.data_profiles import EmbeddingProfile


class GeneratedEmbeddings(NamedTuple):
    """Result from embedding generation."""

    embeddings: npt.NDArray[np.float32]
    labels: npt.NDArray[np.int64]  # True cluster labels (-1 for noise)
    centroids: npt.NDArray[np.float32]  # Cluster centroids


def generate_clusterable_embeddings(
    profile: EmbeddingProfile,
    seed: int = 42,
) -> GeneratedEmbeddings:
    """Generate embeddings with controlled cluster structure.

    Uses tangent-space perturbation for high-dimensional unit vectors,
    which produces realistic angular distribution for cosine similarity.

    Args:
        profile: Embedding profile defining cluster characteristics
        seed: Random seed for reproducibility

    Returns:
        GeneratedEmbeddings with embeddings, true labels, and centroids
    """
    rng = np.random.default_rng(seed)

    # Calculate points per cluster
    n_noise = int(profile.n_points * profile.noise_ratio)
    n_clustered = profile.n_points - n_noise
    points_per_cluster = n_clustered // profile.n_clusters
    remainder = n_clustered % profile.n_clusters

    # Generate cluster centroids with minimum separation
    centroids = _generate_separated_centroids(
        n_clusters=profile.n_clusters,
        dim=profile.embedding_dim,
        min_distance=profile.inter_cluster_distance,
        rng=rng,
    )

    embeddings_list: list[npt.NDArray[np.float32]] = []
    labels: list[int] = []

    # Generate clustered points
    for i, centroid in enumerate(centroids):
        n_points = points_per_cluster + (1 if i < remainder else 0)
        cluster_points = _sample_around_centroid(
            centroid=centroid,
            n_points=n_points,
            spread=profile.cluster_spread,
            dim=profile.embedding_dim,
            rng=rng,
        )
        embeddings_list.append(cluster_points)
        labels.extend([i] * n_points)

    # Generate noise points (uniform on unit sphere)
    if n_noise > 0:
        noise_points = _generate_uniform_sphere(
            n_points=n_noise,
            dim=profile.embedding_dim,
            rng=rng,
        )
        embeddings_list.append(noise_points)
        labels.extend([-1] * n_noise)

    embeddings_array = np.vstack(embeddings_list).astype(np.float32)
    labels_array = np.array(labels, dtype=np.int64)

    # Shuffle to mix noise with clusters
    shuffle_idx = rng.permutation(len(labels_array))

    return GeneratedEmbeddings(
        embeddings=embeddings_array[shuffle_idx],
        labels=labels_array[shuffle_idx],
        centroids=np.array(centroids, dtype=np.float32),
    )


def _generate_separated_centroids(
    n_clusters: int,
    dim: int,
    min_distance: float,
    rng: np.random.Generator,
    max_attempts: int = 1000,
) -> list[npt.NDArray[np.float32]]:
    """Generate cluster centroids with minimum separation.

    Args:
        n_clusters: Number of centroids to generate
        dim: Embedding dimension
        min_distance: Minimum cosine distance between centroids
        rng: Random number generator
        max_attempts: Maximum attempts to place each centroid

    Returns:
        List of unit-normalized centroid vectors
    """
    centroids: list[npt.NDArray[np.float32]] = []

    for _ in range(n_clusters):
        for _ in range(max_attempts):
            candidate_raw = rng.standard_normal(dim)
            candidate_norm = candidate_raw / np.linalg.norm(candidate_raw)
            candidate: npt.NDArray[np.float32] = candidate_norm.astype(np.float32)

            # Check distance to existing centroids (cosine distance = 1 - dot)
            if all(
                1 - np.dot(candidate, c) >= min_distance for c in centroids
            ):
                centroids.append(candidate)
                break
        else:
            # Fallback: add anyway (for high n_clusters in low dim)
            fallback_raw = rng.standard_normal(dim)
            fallback_norm = fallback_raw / np.linalg.norm(fallback_raw)
            fallback: npt.NDArray[np.float32] = fallback_norm.astype(np.float32)
            centroids.append(fallback)

    return centroids


def _sample_around_centroid(
    centroid: npt.NDArray[np.float32],
    n_points: int,
    spread: float,
    dim: int,
    rng: np.random.Generator,
) -> npt.NDArray[np.float32]:
    """Sample points around a centroid with given spread.

    Uses tangent-space perturbation for realistic angular distribution.

    Args:
        centroid: Unit-normalized centroid vector
        n_points: Number of points to sample
        spread: Spread parameter (higher = more spread)
        dim: Embedding dimension
        rng: Random number generator

    Returns:
        Array of shape (n_points, dim) with unit-normalized vectors
    """
    # Generate perturbations in tangent space
    perturbations = rng.standard_normal((n_points, dim)).astype(np.float32)

    # Project out the centroid direction to get tangent vectors
    dots = np.dot(perturbations, centroid)[:, np.newaxis]
    tangent = perturbations - dots * centroid

    # Scale by spread and add to centroid
    tangent_norms = np.linalg.norm(tangent, axis=1, keepdims=True)
    tangent_norms[tangent_norms == 0] = 1  # Avoid division by zero
    scaled_tangent = (
        tangent / tangent_norms * spread * rng.exponential(1, (n_points, 1))
    )

    points = centroid + scaled_tangent

    # Renormalize to unit sphere
    norms = np.linalg.norm(points, axis=1, keepdims=True)
    result: npt.NDArray[np.float32] = (points / norms).astype(np.float32)
    return result


def _generate_uniform_sphere(
    n_points: int,
    dim: int,
    rng: np.random.Generator,
) -> npt.NDArray[np.float32]:
    """Generate points uniformly on unit hypersphere.

    Args:
        n_points: Number of points to generate
        dim: Embedding dimension
        rng: Random number generator

    Returns:
        Array of shape (n_points, dim) with unit-normalized vectors
    """
    points = rng.standard_normal((n_points, dim)).astype(np.float32)
    norms = np.linalg.norm(points, axis=1, keepdims=True)
    result: npt.NDArray[np.float32] = (points / norms).astype(np.float32)
    return result
