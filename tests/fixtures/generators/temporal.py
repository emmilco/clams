"""Temporal pattern generators for validation testing.

This module generates timestamps with realistic temporal patterns
including uniform, burst, decay, and growth distributions.

Reference: SPEC-034 temporal pattern requirements
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import numpy as np
import numpy.typing as npt

from tests.fixtures.data_profiles import TemporalProfile


def generate_temporal_distribution(
    count: int,
    pattern: Literal["uniform", "bursts", "decay", "growth"],
    span_days: int,
    seed: int = 42,
    burst_count: int = 3,
    burst_intensity: float = 5.0,
) -> list[datetime]:
    """Generate timestamps matching the specified pattern.

    Args:
        count: Number of timestamps to generate
        pattern: Distribution pattern
        span_days: Total time span in days
        seed: Random seed for reproducibility
        burst_count: Number of burst periods (for burst pattern)
        burst_intensity: Density multiplier during bursts

    Returns:
        Sorted list of timezone-aware datetime objects

    Raises:
        ValueError: If pattern is unknown
    """
    rng = np.random.default_rng(seed)
    # Use a fixed reference date derived from seed for reproducibility
    # This ensures the same seed always produces the same timestamps
    reference_day = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
    end_time = reference_day + timedelta(days=seed % 365)  # Vary by seed
    start_time = end_time - timedelta(days=span_days)

    offsets: npt.NDArray[np.floating[Any]]

    if pattern == "uniform":
        # Uniform distribution across span
        offsets = rng.uniform(0, span_days * 86400, count)

    elif pattern == "bursts":
        # Generate burst centers
        burst_centers = rng.uniform(0.1, 0.9, burst_count) * span_days * 86400
        burst_widths = span_days * 86400 * 0.05  # 5% of span per burst

        # Mix of burst and background points
        n_burst = int(count * 0.7)
        n_background = count - n_burst

        # Burst points (clustered around burst centers)
        burst_assignments = rng.integers(0, burst_count, n_burst)
        burst_offsets: list[float] = []
        for i in range(n_burst):
            center = burst_centers[burst_assignments[i]]
            offset = center + rng.normal(0, burst_widths)
            burst_offsets.append(max(0.0, min(float(span_days * 86400), offset)))

        # Background points (uniform)
        background_offsets = rng.uniform(0, span_days * 86400, n_background)

        offsets = np.concatenate([burst_offsets, background_offsets])

    elif pattern == "decay":
        # Exponential decay (more recent = more dense)
        # Use inverse transform sampling
        u = rng.uniform(0, 1, count)
        decay_rate = 3.0 / span_days  # ~95% within span
        offsets = (
            -np.log(1 - u * (1 - np.exp(-decay_rate * span_days * 86400))) / decay_rate
        )
        offsets = span_days * 86400 - offsets  # Flip so recent is denser

    elif pattern == "growth":
        # Exponential growth (older = more dense)
        u = rng.uniform(0, 1, count)
        growth_rate = 3.0 / span_days
        offsets = (
            -np.log(1 - u * (1 - np.exp(-growth_rate * span_days * 86400))) / growth_rate
        )

    else:
        raise ValueError(f"Unknown pattern: {pattern}")

    # Convert to datetimes
    timestamps = [
        start_time + timedelta(seconds=float(offset)) for offset in sorted(offsets)
    ]

    return timestamps


def generate_from_profile(profile: TemporalProfile, seed: int = 42) -> list[datetime]:
    """Generate timestamps from a TemporalProfile.

    Args:
        profile: Temporal profile defining characteristics
        seed: Random seed for reproducibility

    Returns:
        Sorted list of timezone-aware datetime objects
    """
    return generate_temporal_distribution(
        count=profile.count,
        pattern=profile.pattern,
        span_days=profile.span_days,
        seed=seed,
        burst_count=profile.burst_count,
        burst_intensity=profile.burst_intensity,
    )
