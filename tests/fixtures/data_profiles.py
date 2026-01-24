"""Production-like data profiles for validation testing.

This module defines dataclasses that formally specify production-like data
characteristics. These profiles are used by generators to create realistic
test data that exercises algorithms the way production data does.

Reference: SPEC-034 - Parameter Validation with Production Data
Reference: BUG-031 - Clustering parameters too conservative for real data

Design Rationale:
    Production data differs from minimal test data in several key ways:
    - Higher counts (50-500 items instead of 3-10)
    - Skewed distributions (not uniform/even)
    - Overlapping themes instead of well-separated clusters
    - Temporal patterns (bursts, not uniform)
    - Variable content lengths and density

    These profiles document expected production characteristics and allow
    generators to produce test data that reveals parameter-tuning issues
    before they reach production.
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class GHAPDataProfile:
    """Defines characteristics of GHAP data to generate.

    Reference: SPEC-034 GHAP table for production-like values.

    Production GHAP data typically has:
    - 20-200 entries accumulated over weeks/months
    - Single dominant theme (many similar debugging sessions)
    - 70% confirmed, 20% falsified, 10% abandoned outcomes
    - Temporal clustering around active development periods
    """

    count: int = 50
    theme_count: int = 3  # Number of distinct themes
    theme_skew: float = 0.7  # Probability mass for dominant theme
    noise_ratio: float = 0.2  # Fraction of outliers

    # Outcome distribution
    confirmed_ratio: float = 0.7
    falsified_ratio: float = 0.2
    # Remaining is abandoned

    # Temporal characteristics
    temporal_span_days: int = 30  # Spread over N days
    temporal_pattern: Literal["uniform", "bursts", "decay"] = "uniform"

    # Domain distribution
    dominant_domain: str = "debugging"
    domain_concentration: float = 0.6  # 60% in dominant domain

    def __post_init__(self) -> None:
        """Validate profile parameters."""
        if not 0 <= self.theme_skew <= 1:
            raise ValueError(f"theme_skew must be 0-1, got {self.theme_skew}")
        if not 0 <= self.noise_ratio <= 1:
            raise ValueError(f"noise_ratio must be 0-1, got {self.noise_ratio}")
        if self.confirmed_ratio + self.falsified_ratio > 1:
            raise ValueError(
                f"confirmed_ratio + falsified_ratio must be <= 1, "
                f"got {self.confirmed_ratio + self.falsified_ratio}"
            )


@dataclass(frozen=True)
class EmbeddingProfile:
    """Defines characteristics of embedding clusters to generate.

    Reference: SPEC-034 Clustering Input table.

    Production embedding data typically has:
    - 20-200 points from accumulated experiences
    - Overlapping clusters (related themes)
    - 10-40% noise/outliers
    - Moderate intra-cluster spread (cosine distance 0.3-0.5)
    """

    n_points: int = 50
    n_clusters: int = 3
    cluster_spread: float = 0.3  # Intra-cluster variance (cosine distance)
    noise_ratio: float = 0.2
    embedding_dim: int = 768

    # Cluster overlap settings
    inter_cluster_distance: float = 0.5  # Minimum distance between centroids
    allow_overlap: bool = True  # Whether clusters can partially overlap


@dataclass(frozen=True)
class MemoryProfile:
    """Defines characteristics of memory corpus to generate.

    Reference: SPEC-034 Memories table.

    Production memory data typically has:
    - 50-500 memories accumulated over time
    - Skewed category distribution (facts dominate)
    - Bimodal importance (many low, few high)
    - Variable content lengths (10-2000 chars)
    """

    count: int = 100
    category_distribution: dict[str, float] = field(
        default_factory=lambda: {"fact": 0.6, "preference": 0.2, "workflow": 0.2}
    )
    importance_distribution: Literal["uniform", "bimodal", "high_skew"] = "bimodal"
    content_length_range: tuple[int, int] = (10, 2000)
    tag_count_range: tuple[int, int] = (0, 10)


@dataclass(frozen=True)
class TemporalProfile:
    """Defines temporal distribution patterns.

    Reference: SPEC-034 temporal pattern requirements.

    Production temporal data typically has:
    - Burst patterns around active development
    - Quiet periods between features
    - Growth or decay patterns over project lifetime
    """

    count: int = 100
    pattern: Literal["uniform", "bursts", "decay", "growth"] = "uniform"
    span_days: int = 90
    burst_count: int = 3  # For burst pattern
    burst_intensity: float = 5.0  # Multiplier for burst density


@dataclass(frozen=True)
class CommitProfile:
    """Defines characteristics of git commits to generate.

    Reference: SPEC-034 Git Commits table.

    Production commit data typically has:
    - 100-10000 commits in active repos
    - Skewed author distribution (80/20 rule)
    - Burst patterns around releases
    - Variable message lengths with conventions
    """

    count: int = 200
    author_count: int = 5
    author_skew: float = 0.8  # Top 20% authors do 80% of commits
    message_length_range: tuple[int, int] = (10, 500)
    files_per_commit_range: tuple[int, int] = (1, 20)
    temporal_pattern: Literal["uniform", "bursts"] = "bursts"


@dataclass(frozen=True)
class CodeUnitProfile:
    """Defines characteristics of code units to generate.

    Reference: SPEC-034 Code Units table.

    Production code data typically has:
    - 500-5000 units per project
    - Log-normal file size distribution (many small, few large)
    - Multiple languages
    - Variable documentation coverage
    """

    count: int = 500
    language_distribution: dict[str, float] = field(
        default_factory=lambda: {"python": 0.6, "typescript": 0.25, "go": 0.15}
    )
    line_count_range: tuple[int, int] = (10, 500)
    nested_depth_range: tuple[int, int] = (1, 5)
    documentation_ratio: float = 0.4  # 40% have docstrings
    unit_type_distribution: dict[str, float] = field(
        default_factory=lambda: {
            "function": 0.5,
            "class": 0.2,
            "method": 0.25,
            "module": 0.05,
        }
    )


# ==============================================================================
# Preset Profiles
# ==============================================================================

# GHAP Presets
# -----------------------------------------------------------------------------

# Preset: Minimal test data (for comparison)
GHAP_MINIMAL = GHAPDataProfile(
    count=5,
    theme_count=3,
    theme_skew=0.33,
    noise_ratio=0.0,
)

# Preset: Production-like GHAP data
GHAP_PRODUCTION = GHAPDataProfile(
    count=100,
    theme_count=3,
    theme_skew=0.7,
    noise_ratio=0.2,
    temporal_span_days=60,
)

# Preset: BUG-031 scenario (single diffuse theme)
# This profile reproduces the conditions that caused BUG-031:
# 63 thematically similar GHAP entries forming a diffuse cloud
GHAP_DIFFUSE_CLOUD = GHAPDataProfile(
    count=63,
    theme_count=1,
    theme_skew=1.0,
    noise_ratio=0.1,
    confirmed_ratio=0.6,
    falsified_ratio=0.3,
)

# Embedding Presets
# -----------------------------------------------------------------------------

# Preset: Well-separated clusters (easy case)
EMBEDDINGS_WELL_SEPARATED = EmbeddingProfile(
    n_points=50,
    n_clusters=3,
    cluster_spread=0.1,
    inter_cluster_distance=0.8,
    noise_ratio=0.05,
)

# Preset: Diffuse single cluster (hard case)
EMBEDDINGS_DIFFUSE = EmbeddingProfile(
    n_points=100,
    n_clusters=1,
    cluster_spread=0.4,
    noise_ratio=0.2,
)

# Preset: Overlapping clusters (realistic case)
EMBEDDINGS_OVERLAPPING = EmbeddingProfile(
    n_points=100,
    n_clusters=4,
    cluster_spread=0.3,
    inter_cluster_distance=0.3,
    allow_overlap=True,
    noise_ratio=0.15,
)

# Memory Presets
# -----------------------------------------------------------------------------

# Preset: Minimal memories
MEMORY_MINIMAL = MemoryProfile(count=10)

# Preset: Production-like memory corpus
MEMORY_PRODUCTION = MemoryProfile(count=500, importance_distribution="bimodal")

# Temporal Presets
# -----------------------------------------------------------------------------

# Preset: Burst pattern (active development)
TEMPORAL_BURST = TemporalProfile(pattern="bursts", burst_count=4)

# Preset: Uniform pattern (steady development)
TEMPORAL_UNIFORM = TemporalProfile(pattern="uniform")

# Commit Presets
# -----------------------------------------------------------------------------

# Preset: Minimal commits
COMMITS_MINIMAL = CommitProfile(count=20, author_count=2)

# Preset: Production-like commits
COMMITS_PRODUCTION = CommitProfile(
    count=500,
    author_count=10,
    author_skew=0.8,
    temporal_pattern="bursts",
)

# Preset: Single author commits
COMMITS_SINGLE_AUTHOR = CommitProfile(
    count=100,
    author_count=1,
    author_skew=1.0,
)

# Code Unit Presets
# -----------------------------------------------------------------------------

# Preset: Minimal code units
CODE_MINIMAL = CodeUnitProfile(count=50)

# Preset: Production-like code units
CODE_PRODUCTION = CodeUnitProfile(
    count=500,
    documentation_ratio=0.4,
)
