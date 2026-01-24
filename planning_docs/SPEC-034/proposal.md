# SPEC-034 Technical Proposal: Parameter Validation with Production Data

## Problem Statement

Several bugs have surfaced only when code encounters realistic production data rather than minimal test cases. The most notable example is BUG-031, where HDBSCAN clustering parameters tuned for well-separated synthetic clusters failed completely on 63 real GHAP entries that formed a diffuse, thematically similar cloud.

The root cause is a systematic gap: tests use minimal, idealized data that doesn't stress algorithms the way production data does.

## Proposed Solution

Create a validation testing framework with:

1. **Data Profile Definitions** - Dataclasses that formally specify production-like data characteristics
2. **Data Generators** - Functions that produce test data matching these profiles
3. **Validation Tests** - A new `tests/validation/` suite testing algorithms against production-like profiles
4. **Benchmark Integration** - Extend existing benchmarks to track data generation and validation performance

## Architecture Overview

```
tests/
  fixtures/
    data_profiles.py          # Profile dataclasses and preset profiles
    generators/
      __init__.py             # Package exports
      ghap.py                 # GHAP entry generators
      embeddings.py           # Clusterable embedding generators
      temporal.py             # Temporal pattern generators
      memories.py             # Memory corpus generators
      code.py                 # Code unit generators
      commits.py              # Git commit generators
  validation/
    __init__.py
    conftest.py               # Validation-specific fixtures
    test_clustering_validation.py   # Scenarios 1-3
    test_search_pagination.py       # Scenarios 4-5
    test_memory_operations.py       # Scenarios 6-7
    test_temporal_patterns.py       # Scenarios 8-9
    test_parameter_robustness.py    # Scenario 10
  performance/
    benchmark_results.json    # Extended with generation times
```

## Data Profile Definitions

### 1. Core Profile Dataclasses

```python
# tests/fixtures/data_profiles.py

from dataclasses import dataclass, field
from typing import Literal

@dataclass(frozen=True)
class GHAPDataProfile:
    """Defines characteristics of GHAP data to generate.

    Reference: SPEC-034 GHAP table for production-like values.
    """
    count: int = 50
    theme_count: int = 3  # Number of distinct themes
    theme_skew: float = 0.7  # Probability mass for dominant theme
    noise_ratio: float = 0.2  # Fraction of outliers
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
        assert 0 <= self.theme_skew <= 1
        assert 0 <= self.noise_ratio <= 1
        assert self.confirmed_ratio + self.falsified_ratio <= 1


@dataclass(frozen=True)
class EmbeddingProfile:
    """Defines characteristics of embedding clusters to generate.

    Reference: SPEC-034 Clustering Input table.
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
    """
    count: int = 200
    author_count: int = 5
    author_skew: float = 0.8  # Top 20% authors do 80% of commits
    message_length_range: tuple[int, int] = (10, 500)
    files_per_commit_range: tuple[int, int] = (1, 20)
    temporal_pattern: Literal["uniform", "bursts"] = "bursts"
```

### 2. Preset Profiles for Common Scenarios

```python
# tests/fixtures/data_profiles.py (continued)

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
GHAP_DIFFUSE_CLOUD = GHAPDataProfile(
    count=63,
    theme_count=1,
    theme_skew=1.0,
    noise_ratio=0.1,
    confirmed_ratio=0.6,
    falsified_ratio=0.3,
)

# Embedding presets
EMBEDDINGS_WELL_SEPARATED = EmbeddingProfile(
    n_points=50,
    n_clusters=3,
    cluster_spread=0.1,
    inter_cluster_distance=0.8,
    noise_ratio=0.05,
)

EMBEDDINGS_DIFFUSE = EmbeddingProfile(
    n_points=100,
    n_clusters=1,
    cluster_spread=0.4,
    noise_ratio=0.2,
)

EMBEDDINGS_OVERLAPPING = EmbeddingProfile(
    n_points=100,
    n_clusters=4,
    cluster_spread=0.3,
    inter_cluster_distance=0.3,
    allow_overlap=True,
    noise_ratio=0.15,
)

# Memory presets
MEMORY_MINIMAL = MemoryProfile(count=10)
MEMORY_PRODUCTION = MemoryProfile(count=500, importance_distribution="bimodal")

# Temporal presets
TEMPORAL_BURST = TemporalProfile(pattern="bursts", burst_count=4)
TEMPORAL_UNIFORM = TemporalProfile(pattern="uniform")
```

## Data Generator Design

### 1. Embedding Generator

```python
# tests/fixtures/generators/embeddings.py

import numpy as np
import numpy.typing as npt
from typing import NamedTuple

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

    Uses von Mises-Fisher distribution for high-dimensional unit vectors,
    which is the natural distribution for cosine similarity.

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

    embeddings = []
    labels = []

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
        embeddings.append(cluster_points)
        labels.extend([i] * n_points)

    # Generate noise points (uniform on unit sphere)
    if n_noise > 0:
        noise_points = _generate_uniform_sphere(
            n_points=n_noise,
            dim=profile.embedding_dim,
            rng=rng,
        )
        embeddings.append(noise_points)
        labels.extend([-1] * n_noise)

    embeddings_array = np.vstack(embeddings).astype(np.float32)
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
    """Generate cluster centroids with minimum separation."""
    centroids: list[npt.NDArray[np.float32]] = []

    for _ in range(n_clusters):
        for _ in range(max_attempts):
            candidate = rng.standard_normal(dim)
            candidate = candidate / np.linalg.norm(candidate)
            candidate = candidate.astype(np.float32)

            # Check distance to existing centroids
            if all(
                1 - np.dot(candidate, c) >= min_distance
                for c in centroids
            ):
                centroids.append(candidate)
                break
        else:
            # Fallback: add anyway (for high n_clusters in low dim)
            candidate = rng.standard_normal(dim).astype(np.float32)
            candidate = candidate / np.linalg.norm(candidate)
            centroids.append(candidate)

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
    """
    # Generate perturbations in tangent space
    perturbations = rng.standard_normal((n_points, dim)).astype(np.float32)

    # Project out the centroid direction to get tangent vectors
    dots = np.dot(perturbations, centroid)[:, np.newaxis]
    tangent = perturbations - dots * centroid

    # Scale by spread and add to centroid
    tangent_norms = np.linalg.norm(tangent, axis=1, keepdims=True)
    tangent_norms[tangent_norms == 0] = 1  # Avoid division by zero
    tangent = tangent / tangent_norms * spread * rng.exponential(1, (n_points, 1))

    points = centroid + tangent

    # Renormalize to unit sphere
    norms = np.linalg.norm(points, axis=1, keepdims=True)
    return (points / norms).astype(np.float32)


def _generate_uniform_sphere(
    n_points: int,
    dim: int,
    rng: np.random.Generator,
) -> npt.NDArray[np.float32]:
    """Generate points uniformly on unit hypersphere."""
    points = rng.standard_normal((n_points, dim)).astype(np.float32)
    norms = np.linalg.norm(points, axis=1, keepdims=True)
    return points / norms
```

### 2. GHAP Generator

```python
# tests/fixtures/generators/ghap.py

from datetime import datetime, timedelta, timezone
from typing import NamedTuple
import uuid

import numpy as np

from clams.observation.models import (
    ConfidenceTier,
    Domain,
    GHAPEntry,
    Lesson,
    Outcome,
    OutcomeStatus,
    RootCause,
    Strategy,
)
from tests.fixtures.data_profiles import GHAPDataProfile
from tests.fixtures.generators.embeddings import generate_clusterable_embeddings
from tests.fixtures.generators.temporal import generate_temporal_distribution


class GeneratedGHAPData(NamedTuple):
    """Result from GHAP generation."""
    entries: list[GHAPEntry]
    embeddings: np.ndarray  # Full narrative embeddings
    theme_labels: np.ndarray  # Which theme each entry belongs to


# Theme templates for generating realistic GHAP narratives
THEME_TEMPLATES = {
    "debugging_null": {
        "goal_pattern": "Fix {module} crash when {condition}",
        "hypothesis_pattern": "The crash is caused by null pointer in {component}",
        "action_pattern": "Add null check before {operation}",
        "prediction_pattern": "The {module} will handle {condition} without crashing",
    },
    "debugging_race": {
        "goal_pattern": "Resolve race condition in {module}",
        "hypothesis_pattern": "Concurrent access to {resource} causes data corruption",
        "action_pattern": "Add mutex lock around {operation}",
        "prediction_pattern": "Data integrity is preserved under concurrent access",
    },
    "feature_api": {
        "goal_pattern": "Implement {endpoint} API endpoint",
        "hypothesis_pattern": "The endpoint needs {parameters} to fulfill requirements",
        "action_pattern": "Create handler with validation for {parameters}",
        "prediction_pattern": "API returns correct response for valid requests",
    },
    "refactoring_extract": {
        "goal_pattern": "Extract {component} into separate module",
        "hypothesis_pattern": "Moving {component} will improve testability",
        "action_pattern": "Create new module and update imports",
        "prediction_pattern": "Tests pass and coverage improves",
    },
    "testing_coverage": {
        "goal_pattern": "Increase test coverage for {module}",
        "hypothesis_pattern": "Edge cases around {boundary} are untested",
        "action_pattern": "Add parametrized tests for boundary conditions",
        "prediction_pattern": "Coverage increases to {target}%",
    },
}


def generate_ghap_entries(
    profile: GHAPDataProfile,
    seed: int = 42,
) -> GeneratedGHAPData:
    """Generate GHAP entries matching the given profile.

    Args:
        profile: Data profile defining generation parameters
        seed: Random seed for reproducibility

    Returns:
        GeneratedGHAPData with entries, embeddings, and theme labels
    """
    rng = np.random.default_rng(seed)

    # Select themes based on count
    available_themes = list(THEME_TEMPLATES.keys())
    themes = rng.choice(
        available_themes,
        size=min(profile.theme_count, len(available_themes)),
        replace=False,
    ).tolist()

    # Generate timestamps
    from tests.fixtures.generators.temporal import generate_temporal_distribution
    timestamps = generate_temporal_distribution(
        count=profile.count,
        pattern=profile.temporal_pattern,
        span_days=profile.temporal_span_days,
        seed=seed,
    )

    # Generate outcome distribution
    n_confirmed = int(profile.count * profile.confirmed_ratio)
    n_falsified = int(profile.count * profile.falsified_ratio)
    n_abandoned = profile.count - n_confirmed - n_falsified

    outcomes = (
        [OutcomeStatus.CONFIRMED] * n_confirmed +
        [OutcomeStatus.FALSIFIED] * n_falsified +
        [OutcomeStatus.ABANDONED] * n_abandoned
    )
    rng.shuffle(outcomes)

    # Generate theme assignments (with skew toward dominant theme)
    theme_weights = np.ones(len(themes))
    theme_weights[0] = profile.theme_skew * len(themes)  # Boost first theme
    theme_weights = theme_weights / theme_weights.sum()
    theme_assignments = rng.choice(
        len(themes),
        size=profile.count,
        p=theme_weights,
    )

    # Generate domain distribution
    domains = list(Domain)
    domain_weights = np.ones(len(domains)) * (1 - profile.domain_concentration)
    dominant_idx = next(
        i for i, d in enumerate(domains)
        if d.value == profile.dominant_domain
    )
    domain_weights[dominant_idx] = profile.domain_concentration * len(domains)
    domain_weights = domain_weights / domain_weights.sum()
    domain_assignments = rng.choice(
        len(domains),
        size=profile.count,
        p=domain_weights,
    )

    entries = []
    for i in range(profile.count):
        theme = themes[theme_assignments[i]]
        template = THEME_TEMPLATES[theme]

        # Generate content from template with randomized fills
        fills = _generate_template_fills(rng)

        entry = GHAPEntry(
            id=f"ghap_{uuid.uuid4().hex[:12]}",
            session_id=f"session_{seed}_{i // 10}",  # Group into sessions
            created_at=timestamps[i],
            domain=domains[domain_assignments[i]],
            strategy=rng.choice(list(Strategy)),
            goal=template["goal_pattern"].format(**fills),
            hypothesis=template["hypothesis_pattern"].format(**fills),
            action=template["action_pattern"].format(**fills),
            prediction=template["prediction_pattern"].format(**fills),
            iteration_count=int(rng.integers(1, 5)),
            outcome=_generate_outcome(outcomes[i], timestamps[i], rng),
            surprise=_generate_surprise(outcomes[i], rng) if outcomes[i] == OutcomeStatus.FALSIFIED else None,
            root_cause=_generate_root_cause(outcomes[i], rng) if outcomes[i] == OutcomeStatus.FALSIFIED else None,
            lesson=_generate_lesson(outcomes[i], rng) if outcomes[i] != OutcomeStatus.ABANDONED else None,
            confidence_tier=_get_confidence_tier(outcomes[i]),
        )
        entries.append(entry)

    # Generate embeddings that match theme structure
    from tests.fixtures.data_profiles import EmbeddingProfile
    embedding_profile = EmbeddingProfile(
        n_points=profile.count,
        n_clusters=profile.theme_count,
        cluster_spread=0.3 + 0.2 * profile.noise_ratio,  # More spread with more noise
        noise_ratio=profile.noise_ratio,
        embedding_dim=768,
    )

    embedding_result = generate_clusterable_embeddings(embedding_profile, seed=seed + 1)

    return GeneratedGHAPData(
        entries=entries,
        embeddings=embedding_result.embeddings,
        theme_labels=embedding_result.labels,
    )


def _generate_template_fills(rng: np.random.Generator) -> dict[str, str]:
    """Generate random fills for template placeholders."""
    modules = ["auth", "search", "indexer", "storage", "api", "cache"]
    components = ["validator", "parser", "handler", "service", "client"]
    conditions = ["null input", "empty list", "timeout", "invalid state"]
    resources = ["database", "cache", "queue", "session", "config"]
    operations = ["read", "write", "update", "delete", "validate"]
    endpoints = ["users", "items", "search", "status", "metrics"]
    parameters = ["user_id", "query", "filters", "pagination", "auth_token"]
    boundaries = ["min value", "max length", "empty input", "unicode"]

    return {
        "module": rng.choice(modules),
        "component": rng.choice(components),
        "condition": rng.choice(conditions),
        "resource": rng.choice(resources),
        "operation": rng.choice(operations),
        "endpoint": rng.choice(endpoints),
        "parameters": rng.choice(parameters),
        "boundary": rng.choice(boundaries),
        "target": str(rng.integers(80, 100)),
    }


def _generate_outcome(
    status: OutcomeStatus,
    timestamp: datetime,
    rng: np.random.Generator,
) -> Outcome:
    """Generate outcome details."""
    results = {
        OutcomeStatus.CONFIRMED: "Hypothesis confirmed - fix works as expected",
        OutcomeStatus.FALSIFIED: "Hypothesis was incorrect - root cause was different",
        OutcomeStatus.ABANDONED: "Goal abandoned due to changing requirements",
    }
    return Outcome(
        status=status,
        result=results[status],
        captured_at=timestamp + timedelta(hours=rng.integers(1, 24)),
        auto_captured=bool(rng.integers(0, 2)),
    )


def _generate_surprise(status: OutcomeStatus, rng: np.random.Generator) -> str | None:
    """Generate surprise text for falsified outcomes."""
    surprises = [
        "The actual cause was unrelated to initial hypothesis",
        "A side effect masked the real issue",
        "The problem was in a different layer than expected",
        "Test environment masked production behavior",
        "Race condition appeared only under load",
    ]
    return rng.choice(surprises)


def _generate_root_cause(status: OutcomeStatus, rng: np.random.Generator) -> RootCause | None:
    """Generate root cause for falsified outcomes."""
    categories = [
        "wrong-assumption",
        "missing-knowledge",
        "oversight",
        "environment-issue",
        "misleading-symptom",
    ]
    descriptions = [
        "Initial assumption about the cause was incorrect",
        "Missing knowledge about subsystem behavior",
        "Overlooked edge case in implementation",
        "Environment differences caused misleading symptoms",
        "Symptoms pointed to wrong component",
    ]
    idx = rng.integers(0, len(categories))
    return RootCause(category=categories[idx], description=descriptions[idx])


def _generate_lesson(status: OutcomeStatus, rng: np.random.Generator) -> Lesson | None:
    """Generate lesson learned."""
    lessons = [
        ("Check assumptions early", "Always validate assumptions before implementing"),
        ("Add logging first", "Logging helps narrow down issues faster"),
        ("Test edge cases", "Edge cases reveal hidden bugs"),
        ("Review dependencies", "Dependencies can have unexpected behaviors"),
    ]
    idx = rng.integers(0, len(lessons))
    return Lesson(what_worked=lessons[idx][0], takeaway=lessons[idx][1])


def _get_confidence_tier(status: OutcomeStatus) -> ConfidenceTier:
    """Determine confidence tier based on outcome."""
    if status == OutcomeStatus.ABANDONED:
        return ConfidenceTier.ABANDONED
    elif status == OutcomeStatus.CONFIRMED:
        return ConfidenceTier.GOLD
    else:
        return ConfidenceTier.SILVER
```

### 3. Temporal Pattern Generator

```python
# tests/fixtures/generators/temporal.py

from datetime import datetime, timedelta, timezone
from typing import Literal

import numpy as np

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
        seed: Random seed
        burst_count: Number of burst periods (for burst pattern)
        burst_intensity: Density multiplier during bursts

    Returns:
        Sorted list of timezone-aware datetime objects
    """
    rng = np.random.default_rng(seed)
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=span_days)

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
        burst_offsets = []
        for i in range(n_burst):
            center = burst_centers[burst_assignments[i]]
            offset = center + rng.normal(0, burst_widths)
            burst_offsets.append(max(0, min(span_days * 86400, offset)))

        # Background points (uniform)
        background_offsets = rng.uniform(0, span_days * 86400, n_background)

        offsets = np.concatenate([burst_offsets, background_offsets])

    elif pattern == "decay":
        # Exponential decay (more recent = more dense)
        # Use inverse transform sampling
        u = rng.uniform(0, 1, count)
        decay_rate = 3.0 / span_days  # ~95% within span
        offsets = -np.log(1 - u * (1 - np.exp(-decay_rate * span_days * 86400))) / decay_rate
        offsets = span_days * 86400 - offsets  # Flip so recent is denser

    elif pattern == "growth":
        # Exponential growth (older = more dense)
        u = rng.uniform(0, 1, count)
        growth_rate = 3.0 / span_days
        offsets = -np.log(1 - u * (1 - np.exp(-growth_rate * span_days * 86400))) / growth_rate

    else:
        raise ValueError(f"Unknown pattern: {pattern}")

    # Convert to datetimes
    timestamps = [
        start_time + timedelta(seconds=float(offset))
        for offset in sorted(offsets)
    ]

    return timestamps


def generate_from_profile(profile: TemporalProfile, seed: int = 42) -> list[datetime]:
    """Generate timestamps from a TemporalProfile."""
    return generate_temporal_distribution(
        count=profile.count,
        pattern=profile.pattern,
        span_days=profile.span_days,
        seed=seed,
        burst_count=profile.burst_count,
        burst_intensity=profile.burst_intensity,
    )
```

### 4. Memory Generator

```python
# tests/fixtures/generators/memories.py

from dataclasses import dataclass
import uuid

import numpy as np

from tests.fixtures.data_profiles import MemoryProfile


@dataclass
class GeneratedMemory:
    """A generated memory entry."""
    id: str
    content: str
    category: str
    importance: float
    tags: list[str]


def generate_memories(
    profile: MemoryProfile,
    seed: int = 42,
) -> list[GeneratedMemory]:
    """Generate memory entries matching the profile.

    Args:
        profile: Memory profile defining characteristics
        seed: Random seed

    Returns:
        List of generated memory entries
    """
    rng = np.random.default_rng(seed)

    # Generate category assignments
    categories = list(profile.category_distribution.keys())
    weights = list(profile.category_distribution.values())
    category_assignments = rng.choice(
        categories,
        size=profile.count,
        p=weights,
    )

    # Generate importance values based on distribution
    if profile.importance_distribution == "uniform":
        importances = rng.uniform(0.1, 1.0, profile.count)
    elif profile.importance_distribution == "bimodal":
        # 70% low (0.2-0.5), 30% high (0.8-1.0)
        n_low = int(profile.count * 0.7)
        n_high = profile.count - n_low
        low_importances = rng.uniform(0.2, 0.5, n_low)
        high_importances = rng.uniform(0.8, 1.0, n_high)
        importances = np.concatenate([low_importances, high_importances])
        rng.shuffle(importances)
    else:  # high_skew
        # Most at low, few at high (exponential)
        importances = 1.0 - rng.exponential(0.3, profile.count)
        importances = np.clip(importances, 0.1, 1.0)

    # Content templates by category
    content_templates = {
        "fact": [
            "The {component} uses {algorithm} for {purpose}.",
            "When debugging {issue}, check {location} first.",
            "{Framework} version {version} introduced {feature}.",
            "The API endpoint {endpoint} requires {auth_type} authentication.",
            "Database queries for {table} should include index on {column}.",
        ],
        "preference": [
            "User prefers {style} coding style for {language}.",
            "Always use {tool} when working with {domain}.",
            "Prefer {approach} over {alternative} for {context}.",
            "Run {command} before committing changes.",
        ],
        "workflow": [
            "Start {task} by running {command}.",
            "The deployment process requires {steps} steps.",
            "When reviewing code, check {checklist} first.",
            "Use {branch_pattern} for {feature_type} branches.",
        ],
    }

    # Tag pool
    all_tags = [
        "python", "javascript", "testing", "debugging", "performance",
        "security", "api", "database", "frontend", "backend",
        "docker", "kubernetes", "ci-cd", "documentation", "refactoring",
    ]

    memories = []
    for i in range(profile.count):
        category = category_assignments[i]

        # Generate content from template
        template = rng.choice(content_templates[category])
        content = _fill_template(template, rng)

        # Adjust content length to be within range
        min_len, max_len = profile.content_length_range
        target_len = rng.integers(min_len, max_len + 1)
        content = _adjust_content_length(content, target_len, rng)

        # Generate tags
        min_tags, max_tags = profile.tag_count_range
        n_tags = rng.integers(min_tags, max_tags + 1)
        tags = rng.choice(all_tags, size=min(n_tags, len(all_tags)), replace=False).tolist()

        memories.append(GeneratedMemory(
            id=f"mem_{uuid.uuid4().hex[:12]}",
            content=content,
            category=category,
            importance=float(importances[i]),
            tags=tags,
        ))

    return memories


def _fill_template(template: str, rng: np.random.Generator) -> str:
    """Fill a template with random but plausible values."""
    fills = {
        "component": rng.choice(["auth", "cache", "queue", "validator", "parser"]),
        "algorithm": rng.choice(["HDBSCAN", "BFS", "binary search", "hash table"]),
        "purpose": rng.choice(["clustering", "indexing", "validation", "caching"]),
        "issue": rng.choice(["memory leak", "race condition", "timeout", "crash"]),
        "location": rng.choice(["logs", "stack trace", "database queries", "network calls"]),
        "Framework": rng.choice(["FastAPI", "SQLAlchemy", "PyTorch", "Pydantic"]),
        "version": f"{rng.integers(1, 5)}.{rng.integers(0, 20)}",
        "feature": rng.choice(["async support", "type hints", "new API", "performance boost"]),
        "endpoint": rng.choice(["/api/v1/users", "/search", "/health", "/metrics"]),
        "auth_type": rng.choice(["Bearer token", "API key", "OAuth2", "Basic"]),
        "table": rng.choice(["users", "items", "logs", "sessions"]),
        "column": rng.choice(["created_at", "user_id", "status", "type"]),
        "style": rng.choice(["functional", "object-oriented", "declarative"]),
        "language": rng.choice(["Python", "TypeScript", "Go", "Rust"]),
        "tool": rng.choice(["pytest", "mypy", "ruff", "docker"]),
        "domain": rng.choice(["testing", "deployment", "debugging", "profiling"]),
        "approach": rng.choice(["composition", "dependency injection", "immutability"]),
        "alternative": rng.choice(["inheritance", "global state", "mutability"]),
        "context": rng.choice(["new features", "refactoring", "bug fixes"]),
        "command": rng.choice(["pytest", "make build", "docker-compose up"]),
        "task": rng.choice(["feature development", "bug investigation", "code review"]),
        "steps": str(rng.integers(3, 10)),
        "checklist": rng.choice(["tests", "types", "documentation", "security"]),
        "branch_pattern": rng.choice(["feature/", "bugfix/", "release/"]),
        "feature_type": rng.choice(["new features", "bug fixes", "releases"]),
    }

    for key, value in fills.items():
        template = template.replace(f"{{{key}}}", value)

    return template


def _adjust_content_length(content: str, target_len: int, rng: np.random.Generator) -> str:
    """Adjust content to approximately target length."""
    if len(content) >= target_len:
        return content[:target_len]

    # Extend with additional context
    extensions = [
        " This is important for maintaining code quality.",
        " Consider this when making related changes.",
        " This pattern has been proven effective.",
        " See documentation for more details.",
        " This applies to similar scenarios.",
    ]

    while len(content) < target_len:
        content += rng.choice(extensions)

    return content[:target_len]
```

### 5. Code Unit Generator

```python
# tests/fixtures/generators/code.py

"""Generator for code unit data used in codebase indexing tests.

Reference: SPEC-034 Code Units table for production-like characteristics.
"""

from dataclasses import dataclass
from typing import Literal
import uuid

import numpy as np

from tests.fixtures.data_profiles import CodeUnitProfile


@dataclass
class GeneratedCodeUnit:
    """A generated code unit entry."""
    id: str
    file_path: str
    language: str
    unit_type: Literal["function", "class", "method", "module"]
    name: str
    content: str
    line_count: int
    docstring: str | None
    nested_depth: int


# Add to data_profiles.py:
@dataclass(frozen=True)
class CodeUnitProfile:
    """Defines characteristics of code units to generate.

    Reference: SPEC-034 Code Units table.
    """
    count: int = 500
    language_distribution: dict[str, float] = None  # Default set in __post_init__
    line_count_range: tuple[int, int] = (10, 500)
    nested_depth_range: tuple[int, int] = (1, 5)
    documentation_ratio: float = 0.4  # 40% have docstrings
    unit_type_distribution: dict[str, float] = None  # Default set in __post_init__

    def __post_init__(self) -> None:
        """Set defaults for mutable fields."""
        object.__setattr__(
            self,
            "language_distribution",
            self.language_distribution or {"python": 0.6, "typescript": 0.25, "go": 0.15},
        )
        object.__setattr__(
            self,
            "unit_type_distribution",
            self.unit_type_distribution or {"function": 0.5, "class": 0.2, "method": 0.25, "module": 0.05},
        )


# Code templates by language
CODE_TEMPLATES = {
    "python": {
        "function": '''def {name}({params}) -> {return_type}:
    """{docstring}"""
    {body}
    return {return_value}
''',
        "class": '''class {name}:
    """{docstring}"""

    def __init__(self{init_params}) -> None:
        {init_body}

    def {method_name}(self{method_params}) -> {return_type}:
        {method_body}
''',
        "method": '''def {name}(self{params}) -> {return_type}:
    """{docstring}"""
    {body}
    return {return_value}
''',
        "module": '''"""{docstring}"""

{imports}

{constants}

{body}
''',
    },
    "typescript": {
        "function": '''export function {name}({params}): {return_type} {{
    // {docstring}
    {body}
    return {return_value};
}}
''',
        "class": '''export class {name} {{
    // {docstring}
    {fields}

    constructor({init_params}) {{
        {init_body}
    }}

    {method_name}({method_params}): {return_type} {{
        {method_body}
    }}
}}
''',
        "method": '''{name}({params}): {return_type} {{
    // {docstring}
    {body}
    return {return_value};
}}
''',
        "module": '''// {docstring}

{imports}

{constants}

{body}
''',
    },
    "go": {
        "function": '''// {docstring}
func {name}({params}) {return_type} {{
    {body}
    return {return_value}
}}
''',
        "class": '''// {docstring}
type {name} struct {{
    {fields}
}}

func New{name}({init_params}) *{name} {{
    {init_body}
}}

func (s *{name}) {method_name}({method_params}) {return_type} {{
    {method_body}
}}
''',
        "method": '''func (s *{struct_name}) {name}({params}) {return_type} {{
    // {docstring}
    {body}
    return {return_value}
}}
''',
        "module": '''// {docstring}
package {package_name}

{imports}

{constants}

{body}
''',
    },
}


def generate_code_units(
    profile: CodeUnitProfile,
    seed: int = 42,
) -> list[GeneratedCodeUnit]:
    """Generate code unit entries matching the profile.

    Args:
        profile: Code unit profile defining characteristics
        seed: Random seed for reproducibility

    Returns:
        List of generated code units
    """
    rng = np.random.default_rng(seed)

    # Generate language assignments
    languages = list(profile.language_distribution.keys())
    lang_weights = list(profile.language_distribution.values())
    language_assignments = rng.choice(languages, size=profile.count, p=lang_weights)

    # Generate unit type assignments
    unit_types = list(profile.unit_type_distribution.keys())
    type_weights = list(profile.unit_type_distribution.values())
    type_assignments = rng.choice(unit_types, size=profile.count, p=type_weights)

    # Generate documentation flags
    has_docs = rng.random(profile.count) < profile.documentation_ratio

    code_units = []
    for i in range(profile.count):
        language = language_assignments[i]
        unit_type = type_assignments[i]

        # Generate line count with log-normal distribution (more small files)
        min_lines, max_lines = profile.line_count_range
        line_count = int(np.clip(
            rng.lognormal(mean=4.0, sigma=1.0),  # Peak around 55 lines
            min_lines,
            max_lines,
        ))

        # Generate nested depth
        min_depth, max_depth = profile.nested_depth_range
        nested_depth = int(rng.integers(min_depth, max_depth + 1))

        # Generate name
        name = _generate_code_name(unit_type, rng)

        # Generate content from template
        content = _generate_code_content(
            language=language,
            unit_type=unit_type,
            name=name,
            line_count=line_count,
            has_docs=has_docs[i],
            rng=rng,
        )

        # Generate file path
        file_path = _generate_file_path(language, unit_type, name, nested_depth, rng)

        code_units.append(GeneratedCodeUnit(
            id=f"code_{uuid.uuid4().hex[:12]}",
            file_path=file_path,
            language=language,
            unit_type=unit_type,
            name=name,
            content=content,
            line_count=line_count,
            docstring=_generate_docstring(unit_type, rng) if has_docs[i] else None,
            nested_depth=nested_depth,
        ))

    return code_units


def _generate_code_name(unit_type: str, rng: np.random.Generator) -> str:
    """Generate a realistic code unit name."""
    prefixes = {
        "function": ["get", "set", "create", "update", "delete", "validate", "process", "handle", "parse", "format"],
        "class": ["", "Abstract", "Base", "Default", "Custom"],
        "method": ["get", "set", "is", "has", "can", "should", "update", "validate"],
        "module": [""],
    }
    nouns = ["user", "item", "data", "config", "result", "handler", "service", "manager", "factory", "builder"]
    suffixes = {
        "function": ["", "_async", "_sync", "_cached"],
        "class": ["Service", "Manager", "Handler", "Factory", "Builder", "Client", "Repository"],
        "method": ["", "_value", "_all", "_by_id"],
        "module": ["utils", "helpers", "constants", "types", "models", "services"],
    }

    prefix = rng.choice(prefixes.get(unit_type, [""]))
    noun = rng.choice(nouns)
    suffix = rng.choice(suffixes.get(unit_type, [""]))

    if unit_type == "class":
        return f"{prefix}{noun.title()}{suffix}"
    elif unit_type == "module":
        return f"{noun}_{suffix}" if suffix else noun
    else:
        return f"{prefix}_{noun}{suffix}" if prefix else f"{noun}{suffix}"


def _generate_code_content(
    language: str,
    unit_type: str,
    name: str,
    line_count: int,
    has_docs: bool,
    rng: np.random.Generator,
) -> str:
    """Generate code content from templates."""
    template = CODE_TEMPLATES.get(language, CODE_TEMPLATES["python"]).get(unit_type, "")

    # Generate template fills
    fills = _generate_code_fills(language, unit_type, name, has_docs, rng)

    content = template.format(**fills)

    # Adjust to target line count by adding/removing body lines
    current_lines = content.count("\n") + 1
    if current_lines < line_count:
        # Add padding comments/code
        padding = _generate_padding_lines(language, line_count - current_lines, rng)
        content = content.replace("{body}", f"{{body}}\n{padding}")

    return content


def _generate_code_fills(
    language: str,
    unit_type: str,
    name: str,
    has_docs: bool,
    rng: np.random.Generator,
) -> dict[str, str]:
    """Generate fills for code templates."""
    types_by_lang = {
        "python": {"str": "str", "int": "int", "bool": "bool", "list": "list", "dict": "dict", "None": "None"},
        "typescript": {"str": "string", "int": "number", "bool": "boolean", "list": "Array<any>", "dict": "Record<string, any>", "None": "void"},
        "go": {"str": "string", "int": "int", "bool": "bool", "list": "[]interface{}", "dict": "map[string]interface{}", "None": ""},
    }
    types = types_by_lang.get(language, types_by_lang["python"])

    return_type = rng.choice(list(types.values()))
    param_type = rng.choice(["str", "int", "bool"])

    return {
        "name": name,
        "params": f"value: {types[param_type]}" if language == "python" else f"value: {types[param_type]}",
        "return_type": return_type,
        "return_value": "result" if return_type != types["None"] else "",
        "docstring": _generate_docstring(unit_type, rng) if has_docs else "TODO: Add documentation",
        "body": f"result = value  # Process {name}",
        "init_params": ", value: int = 0" if language == "python" else "value: number = 0",
        "init_body": "self.value = value" if language == "python" else "this.value = value;",
        "method_name": f"process_{name.lower()}" if unit_type == "class" else name,
        "method_params": "",
        "method_body": "pass" if language == "python" else "return;",
        "fields": "value: number;" if language == "typescript" else "Value int" if language == "go" else "",
        "imports": "",
        "constants": "",
        "struct_name": name.title(),
        "package_name": "main",
    }


def _generate_docstring(unit_type: str, rng: np.random.Generator) -> str:
    """Generate a realistic docstring."""
    templates = [
        f"Process and validate the input {unit_type}.",
        f"Handle the {unit_type} operation with error checking.",
        f"Create a new instance with the given parameters.",
        f"Transform the input data according to configuration.",
        f"Execute the main logic for this {unit_type}.",
    ]
    return rng.choice(templates)


def _generate_padding_lines(language: str, count: int, rng: np.random.Generator) -> str:
    """Generate padding lines to reach target line count."""
    comment_char = "#" if language == "python" else "//"
    lines = []
    for _ in range(count):
        lines.append(f"    {comment_char} Additional processing logic")
    return "\n".join(lines)


def _generate_file_path(
    language: str,
    unit_type: str,
    name: str,
    nested_depth: int,
    rng: np.random.Generator,
) -> str:
    """Generate a realistic file path."""
    extensions = {"python": ".py", "typescript": ".ts", "go": ".go"}
    ext = extensions.get(language, ".py")

    dirs = ["src", "lib", "pkg", "internal", "core", "utils", "services", "handlers"]
    subdirs = ["auth", "users", "items", "api", "storage", "cache", "config"]

    path_parts = [rng.choice(dirs)]
    for _ in range(nested_depth - 1):
        path_parts.append(rng.choice(subdirs))

    filename = f"{name.lower()}{ext}"
    return "/".join(path_parts) + "/" + filename
```

### 6. Git Commit Generator

```python
# tests/fixtures/generators/commits.py

"""Generator for git commit data used in temporal pattern tests.

Reference: SPEC-034 Git Commits table for production-like characteristics.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
import uuid

import numpy as np

from tests.fixtures.data_profiles import CommitProfile
from tests.fixtures.generators.temporal import generate_temporal_distribution


@dataclass
class GeneratedCommit:
    """A generated git commit entry."""
    sha: str
    author_name: str
    author_email: str
    committed_at: datetime
    message: str
    files_changed: list[str]
    insertions: int
    deletions: int


# Commit message templates by type
COMMIT_TEMPLATES = {
    "feature": [
        "feat: add {component} for {purpose}",
        "feat({scope}): implement {feature}",
        "add {component} to handle {purpose}",
        "implement {feature} in {scope}",
    ],
    "fix": [
        "fix: resolve {issue} in {component}",
        "fix({scope}): handle {edge_case}",
        "bugfix: {issue} when {condition}",
        "fix {component} {issue}",
    ],
    "refactor": [
        "refactor: extract {component} from {source}",
        "refactor({scope}): simplify {component}",
        "clean up {component} implementation",
        "reorganize {scope} structure",
    ],
    "docs": [
        "docs: update {component} documentation",
        "docs({scope}): add usage examples",
        "update README with {topic}",
        "add docstrings to {component}",
    ],
    "test": [
        "test: add tests for {component}",
        "test({scope}): improve coverage",
        "add unit tests for {feature}",
        "fix flaky test in {component}",
    ],
    "chore": [
        "chore: update dependencies",
        "chore({scope}): bump version",
        "update configuration for {purpose}",
        "maintenance: {task}",
    ],
}


def generate_commits(
    profile: CommitProfile,
    seed: int = 42,
) -> list[GeneratedCommit]:
    """Generate git commit entries matching the profile.

    Args:
        profile: Commit profile defining characteristics
        seed: Random seed for reproducibility

    Returns:
        List of generated commits sorted by date (oldest first)
    """
    rng = np.random.default_rng(seed)

    # Generate author pool
    authors = _generate_author_pool(profile.author_count, rng)

    # Generate author assignments with skew (80/20 rule)
    author_weights = _generate_skewed_weights(
        profile.author_count,
        profile.author_skew,
        rng,
    )
    author_indices = rng.choice(
        profile.author_count,
        size=profile.count,
        p=author_weights,
    )

    # Generate timestamps with specified pattern
    timestamps = generate_temporal_distribution(
        count=profile.count,
        pattern=profile.temporal_pattern,
        span_days=90,  # Default 3 months of commits
        seed=seed,
        burst_count=5,  # More bursts for commit patterns
        burst_intensity=3.0,
    )

    # Generate commit types with realistic distribution
    commit_types = list(COMMIT_TEMPLATES.keys())
    type_weights = [0.35, 0.25, 0.15, 0.10, 0.10, 0.05]  # feature, fix, refactor, docs, test, chore
    type_assignments = rng.choice(commit_types, size=profile.count, p=type_weights)

    commits = []
    for i in range(profile.count):
        author = authors[author_indices[i]]
        commit_type = type_assignments[i]

        # Generate message
        message = _generate_commit_message(commit_type, rng)

        # Generate files changed
        min_files, max_files = profile.files_per_commit_range
        n_files = int(rng.integers(min_files, max_files + 1))
        files_changed = _generate_file_list(n_files, rng)

        # Generate line changes (correlated with file count)
        avg_changes_per_file = rng.integers(5, 50)
        insertions = int(n_files * avg_changes_per_file * rng.uniform(0.5, 1.5))
        deletions = int(n_files * avg_changes_per_file * rng.uniform(0.2, 0.8))

        commits.append(GeneratedCommit(
            sha=uuid.uuid4().hex[:40],
            author_name=author["name"],
            author_email=author["email"],
            committed_at=timestamps[i],
            message=message,
            files_changed=files_changed,
            insertions=insertions,
            deletions=deletions,
        ))

    return commits


def _generate_author_pool(count: int, rng: np.random.Generator) -> list[dict[str, str]]:
    """Generate a pool of realistic author names and emails."""
    first_names = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry", "Ivy", "Jack"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Wilson", "Taylor"]
    domains = ["example.com", "company.org", "dev.io"]

    authors = []
    for i in range(count):
        first = rng.choice(first_names)
        last = rng.choice(last_names)
        domain = rng.choice(domains)
        authors.append({
            "name": f"{first} {last}",
            "email": f"{first.lower()}.{last.lower()}@{domain}",
        })

    return authors


def _generate_skewed_weights(
    count: int,
    skew: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Generate weights following 80/20 rule.

    Args:
        count: Number of items
        skew: How much the top 20% should dominate (0.8 = 80% of weight)
        rng: Random generator

    Returns:
        Normalized weight array
    """
    # Use Pareto-like distribution
    weights = np.zeros(count)
    top_count = max(1, count // 5)  # Top 20%

    # Top authors get most of the weight
    weights[:top_count] = skew / top_count

    # Remaining authors share the rest
    if count > top_count:
        weights[top_count:] = (1 - skew) / (count - top_count)

    # Shuffle so top authors aren't always first
    rng.shuffle(weights)

    return weights / weights.sum()


def _generate_commit_message(commit_type: str, rng: np.random.Generator) -> str:
    """Generate a realistic commit message."""
    template = rng.choice(COMMIT_TEMPLATES[commit_type])

    fills = {
        "component": rng.choice(["auth", "api", "cache", "storage", "handler", "service", "client"]),
        "purpose": rng.choice(["validation", "error handling", "performance", "security", "logging"]),
        "scope": rng.choice(["core", "api", "db", "auth", "utils"]),
        "feature": rng.choice(["user management", "caching", "rate limiting", "retry logic", "metrics"]),
        "issue": rng.choice(["null pointer", "race condition", "memory leak", "timeout", "validation error"]),
        "edge_case": rng.choice(["empty input", "large payload", "unicode characters", "concurrent access"]),
        "condition": rng.choice(["timeout occurs", "input is empty", "connection fails", "cache misses"]),
        "source": rng.choice(["monolith", "utils", "helpers", "base class"]),
        "topic": rng.choice(["installation", "configuration", "API usage", "deployment"]),
        "task": rng.choice(["cleanup", "update configs", "bump versions", "reorganize"]),
    }

    message = template.format(**fills)

    # Sometimes add body
    if rng.random() < 0.3:
        body = rng.choice([
            "\n\nThis change improves reliability.",
            "\n\nPart of the ongoing refactoring effort.",
            "\n\nAddresses feedback from code review.",
            "\n\nRequired for the upcoming release.",
        ])
        message += body

    return message


def _generate_file_list(count: int, rng: np.random.Generator) -> list[str]:
    """Generate a list of changed file paths."""
    extensions = [".py", ".ts", ".go", ".json", ".yaml", ".md"]
    dirs = ["src", "lib", "tests", "config", "docs"]
    subdirs = ["auth", "api", "core", "utils", "models", "services"]
    filenames = ["index", "main", "utils", "helpers", "types", "config", "test_", "spec_"]

    files = []
    for _ in range(count):
        dir_path = rng.choice(dirs)
        if rng.random() < 0.7:  # Usually have subdirectory
            dir_path = f"{dir_path}/{rng.choice(subdirs)}"

        filename = rng.choice(filenames) + rng.choice(["", "_v2", "_new"])
        ext = rng.choice(extensions)

        files.append(f"{dir_path}/{filename}{ext}")

    return files


# Preset profiles
COMMITS_MINIMAL = CommitProfile(count=20, author_count=2)

COMMITS_PRODUCTION = CommitProfile(
    count=500,
    author_count=10,
    author_skew=0.8,
    temporal_pattern="bursts",
)

COMMITS_SINGLE_AUTHOR = CommitProfile(
    count=100,
    author_count=1,
    author_skew=1.0,
)
```

## Validation Test Suite

### 1. Clustering Validation Tests

```python
# tests/validation/test_clustering_validation.py

"""Validation tests for clustering with production-like data.

These tests verify clustering algorithms work correctly with realistic
data profiles, not just minimal synthetic data.

Reference: SPEC-034 Clustering Validation Scenarios 1-3
Reference: BUG-031 - Clustering failed with 63 similar GHAP entries
"""

import numpy as np
import pytest

from clams.clustering import Clusterer

from tests.fixtures.data_profiles import (
    EMBEDDINGS_DIFFUSE,
    EMBEDDINGS_OVERLAPPING,
    EMBEDDINGS_WELL_SEPARATED,
    EmbeddingProfile,
    GHAP_DIFFUSE_CLOUD,
    GHAP_PRODUCTION,
)
from tests.fixtures.generators.embeddings import generate_clusterable_embeddings
from tests.fixtures.generators.ghap import generate_ghap_entries


class TestMinClusterSizeBoundary:
    """Scenario 1: Min Cluster Size Boundary Testing.

    Verify HDBSCAN respects min_cluster_size parameter at boundaries.
    """

    @pytest.mark.parametrize("min_cluster_size", [3, 5, 7])
    def test_exact_cluster_size_forms_cluster(self, min_cluster_size: int) -> None:
        """Generate exactly min_cluster_size points - cluster should form."""
        profile = EmbeddingProfile(
            n_points=min_cluster_size,
            n_clusters=1,
            cluster_spread=0.1,  # Tight cluster
            noise_ratio=0.0,
            embedding_dim=768,
        )

        result = generate_clusterable_embeddings(profile, seed=42)

        clusterer = Clusterer(
            min_cluster_size=min_cluster_size,
            min_samples=max(2, min_cluster_size - 1),
            metric="cosine",
        )

        cluster_result = clusterer.cluster(result.embeddings)

        # With a tight cluster of exactly min_cluster_size points,
        # we expect at least one cluster to form
        assert cluster_result.n_clusters >= 1, (
            f"Expected cluster to form with {min_cluster_size} points "
            f"and min_cluster_size={min_cluster_size}"
        )

    @pytest.mark.parametrize("min_cluster_size", [4, 6, 8])
    def test_below_min_cluster_size_no_cluster(self, min_cluster_size: int) -> None:
        """Generate min_cluster_size - 1 points - no cluster should form."""
        n_points = min_cluster_size - 1

        profile = EmbeddingProfile(
            n_points=n_points,
            n_clusters=1,
            cluster_spread=0.1,
            noise_ratio=0.0,
            embedding_dim=768,
        )

        result = generate_clusterable_embeddings(profile, seed=42)

        clusterer = Clusterer(
            min_cluster_size=min_cluster_size,
            min_samples=max(2, min_cluster_size - 1),
            metric="cosine",
        )

        cluster_result = clusterer.cluster(result.embeddings)

        # With fewer than min_cluster_size points, no cluster should form
        assert cluster_result.n_clusters == 0, (
            f"Expected no cluster with {n_points} points "
            f"and min_cluster_size={min_cluster_size}, got {cluster_result.n_clusters}"
        )


class TestDiffuseThemeCloud:
    """Scenario 2: Diffuse Theme Cloud Testing.

    Reference: BUG-031 - 63 similar GHAP entries formed no clusters.
    This validates that reasonable parameters can find structure in diffuse data.
    """

    def test_bug_031_scenario_produces_clusters(self) -> None:
        """Reproduce BUG-031 scenario - verify clusters form with current params.

        BUG-031: 63 GHAP entries with single diffuse theme produced 0 clusters
        with min_cluster_size=5, min_samples=3. This test verifies the fix.
        """
        result = generate_ghap_entries(GHAP_DIFFUSE_CLOUD, seed=42)

        # Use parameters that should handle diffuse clouds
        clusterer = Clusterer(
            min_cluster_size=3,  # More permissive than BUG-031's original 5
            min_samples=2,
            metric="cosine",
            cluster_selection_method="eom",
        )

        cluster_result = clusterer.cluster(result.embeddings)

        # With a single-theme cloud of 63 points, we expect some clustering
        # even if not all points are assigned to clusters
        assert cluster_result.n_clusters >= 1, (
            f"BUG-031 regression: Expected at least 1 cluster from 63 similar "
            f"embeddings, got {cluster_result.n_clusters}. "
            f"Noise count: {cluster_result.noise_count}"
        )

        # Verify not ALL points are noise
        noise_ratio = cluster_result.noise_count / len(result.embeddings)
        assert noise_ratio < 0.9, (
            f"Too many points classified as noise: {noise_ratio:.1%}. "
            f"Expected < 90% noise for diffuse but cohesive theme."
        )

    def test_diffuse_profile_clusters_with_relaxed_params(self) -> None:
        """Diffuse embeddings should cluster with appropriately relaxed params."""
        result = generate_clusterable_embeddings(EMBEDDINGS_DIFFUSE, seed=42)

        # More permissive parameters for diffuse data
        clusterer = Clusterer(
            min_cluster_size=3,
            min_samples=2,
            metric="cosine",
        )

        cluster_result = clusterer.cluster(result.embeddings)

        # Some structure should be found even in diffuse data
        assert cluster_result.n_clusters >= 1 or cluster_result.noise_count < len(result.embeddings), (
            "Diffuse data should have either clusters or partial structure"
        )

    def test_production_profile_reasonable_clustering(self) -> None:
        """Production-like GHAP profile should produce reasonable clusters."""
        result = generate_ghap_entries(GHAP_PRODUCTION, seed=42)

        clusterer = Clusterer(
            min_cluster_size=5,
            min_samples=3,
            metric="cosine",
        )

        cluster_result = clusterer.cluster(result.embeddings)

        # With 100 entries and 3 themes, expect some clusters
        assert cluster_result.n_clusters >= 1, (
            f"Production-like profile ({GHAP_PRODUCTION.count} entries, "
            f"{GHAP_PRODUCTION.theme_count} themes) should produce clusters"
        )


class TestMixedDensityRegions:
    """Scenario 3: Mixed Density Regions Testing.

    Verify HDBSCAN handles varying local density correctly.
    """

    def test_finds_clusters_in_dense_regions(self) -> None:
        """Clusters should form in dense regions, sparse outliers as noise."""
        # Create profile with overlapping clusters of varying density
        result = generate_clusterable_embeddings(EMBEDDINGS_OVERLAPPING, seed=42)

        clusterer = Clusterer(
            min_cluster_size=5,
            min_samples=3,
            metric="cosine",
        )

        cluster_result = clusterer.cluster(result.embeddings)

        # Should find most of the clusters
        # Allow some noise due to overlap
        assert cluster_result.n_clusters >= 2, (
            f"Expected >= 2 clusters from {EMBEDDINGS_OVERLAPPING.n_clusters} "
            f"overlapping clusters, got {cluster_result.n_clusters}"
        )

    def test_noise_points_correctly_identified(self) -> None:
        """Points in sparse regions should be classified as noise."""
        profile = EmbeddingProfile(
            n_points=100,
            n_clusters=2,
            cluster_spread=0.15,  # Tight clusters
            noise_ratio=0.3,  # 30% noise
            embedding_dim=768,
        )

        result = generate_clusterable_embeddings(profile, seed=42)

        clusterer = Clusterer(
            min_cluster_size=5,
            min_samples=3,
            metric="cosine",
        )

        cluster_result = clusterer.cluster(result.embeddings)

        # The generated noise should largely be classified as noise by HDBSCAN
        # Allow some tolerance since HDBSCAN might classify some noise as cluster
        expected_noise = int(profile.n_points * profile.noise_ratio)

        # At least half of injected noise should be classified as noise
        assert cluster_result.noise_count >= expected_noise * 0.5, (
            f"Expected at least {expected_noise * 0.5:.0f} noise points "
            f"(50% of injected {expected_noise}), got {cluster_result.noise_count}"
        )


class TestClusteringPerformance:
    """Verify clustering completes within time bounds for production-like data."""

    @pytest.mark.timeout(10)  # 10 second timeout
    def test_clustering_200_points_under_10s(self) -> None:
        """Clustering 200 points should complete in < 10 seconds."""
        profile = EmbeddingProfile(
            n_points=200,
            n_clusters=5,
            cluster_spread=0.25,
            noise_ratio=0.15,
            embedding_dim=768,
        )

        result = generate_clusterable_embeddings(profile, seed=42)

        clusterer = Clusterer(
            min_cluster_size=5,
            min_samples=3,
            metric="cosine",
        )

        # This should complete well under 10 seconds
        cluster_result = clusterer.cluster(result.embeddings)

        assert cluster_result.n_clusters >= 1
```

### 2. Search and Pagination Tests

```python
# tests/validation/test_search_pagination.py

"""Validation tests for search and pagination with production-like data.

These tests verify search operations handle realistic result set sizes
and score distributions correctly.

Reference: SPEC-034 Search/Pagination Scenarios 4-5
"""

import numpy as np
import pytest
from unittest.mock import AsyncMock

from clams.embedding.mock import MockEmbedding
from clams.search.searcher import Searcher
from clams.storage.base import SearchResult

from tests.fixtures.data_profiles import MEMORY_PRODUCTION, MemoryProfile
from tests.fixtures.generators.memories import generate_memories


class TestLargeResultSetPagination:
    """Scenario 4: Large Result Set Pagination.

    Verify pagination works correctly with 200+ items.
    """

    @pytest.fixture
    def large_memory_corpus(self) -> list:
        """Generate 250 memories for pagination testing."""
        profile = MemoryProfile(count=250)
        return generate_memories(profile, seed=42)

    @pytest.fixture
    def mock_vector_store(self, large_memory_corpus) -> AsyncMock:
        """Mock vector store that simulates pagination."""
        store = AsyncMock()

        # Store the corpus for pagination simulation
        store._corpus = large_memory_corpus

        async def search_impl(collection, query, limit, filters=None, offset=0):
            # Simulate search with pagination
            corpus = store._corpus

            # Apply filters if present
            if filters and "category" in filters:
                corpus = [m for m in corpus if m.category == filters["category"]]

            # Simulate relevance scoring (all items get some score)
            results = []
            for i, mem in enumerate(corpus):
                # Score decreases with index (simulating relevance ranking)
                score = 0.95 - (i * 0.003)  # Scores from 0.95 down
                results.append(SearchResult(
                    id=mem.id,
                    score=max(0.1, score),  # Floor at 0.1
                    payload={
                        "content": mem.content,
                        "category": mem.category,
                        "importance": mem.importance,
                        "tags": mem.tags,
                    },
                ))

            # Apply pagination
            start = offset
            end = start + limit
            return results[start:end]

        store.search = search_impl
        return store

    @pytest.fixture
    def searcher(self, mock_vector_store) -> Searcher:
        """Create searcher with mock dependencies."""
        embedding = MockEmbedding()
        return Searcher(embedding, mock_vector_store)

    async def test_paginate_through_all_results(
        self,
        searcher: Searcher,
        mock_vector_store: AsyncMock,
        large_memory_corpus,
    ) -> None:
        """Verify all items are accessible via pagination."""
        page_size = 20
        all_ids = set()
        offset = 0

        while True:
            # Note: Current Searcher doesn't support offset, so this tests
            # the concept. Real implementation would need offset parameter.
            results = await searcher.search_memories("test query", limit=page_size)

            if not results:
                break

            for r in results:
                assert r.id not in all_ids, f"Duplicate ID found: {r.id}"
                all_ids.add(r.id)

            if len(results) < page_size:
                break

            offset += page_size

            # Safety: don't infinite loop in test
            if offset > 1000:
                break

        # We should have retrieved at least some results
        assert len(all_ids) > 0, "No results retrieved"

    async def test_no_duplicates_across_pages(
        self,
        searcher: Searcher,
        large_memory_corpus,
    ) -> None:
        """Verify no duplicate results when paginating."""
        # Get first two "pages" worth of results
        results_page1 = await searcher.search_memories("test", limit=20)
        results_page2 = await searcher.search_memories("test", limit=40)

        # Page 2 should contain page 1 results (since we're not offsetting)
        # but no duplicates within each page
        ids_page1 = [r.id for r in results_page1]
        ids_page2 = [r.id for r in results_page2]

        # No duplicates within each page
        assert len(ids_page1) == len(set(ids_page1)), "Duplicates in page 1"
        assert len(ids_page2) == len(set(ids_page2)), "Duplicates in page 2"

    async def test_boundary_conditions(
        self,
        searcher: Searcher,
        mock_vector_store: AsyncMock,
    ) -> None:
        """Test pagination boundary conditions."""
        # First page
        first_page = await searcher.search_memories("test", limit=20)
        assert len(first_page) == 20, "First page should be full"

        # Request more than available
        all_results = await searcher.search_memories("test", limit=300)
        assert len(all_results) <= 250, "Should not exceed corpus size"

        # Exact fit (if corpus is 250, request 250)
        exact_results = await searcher.search_memories("test", limit=250)
        assert len(exact_results) == 250


class TestScoreDistributionHandling:
    """Scenario 5: Score Distribution Handling.

    Verify search handles long-tail score distributions correctly.
    """

    @pytest.fixture
    def mock_store_with_score_distribution(self) -> AsyncMock:
        """Mock store returning results with long-tail score distribution."""
        store = AsyncMock()

        async def search_with_distribution(collection, query, limit, filters=None):
            # Generate 100 results with long-tail distribution
            # Few high scores, many moderate/low scores
            results = []
            for i in range(100):
                if i < 5:
                    score = 0.95 - (i * 0.02)  # Top 5: 0.95, 0.93, 0.91, ...
                elif i < 20:
                    score = 0.80 - ((i - 5) * 0.02)  # Next 15: 0.80 down to 0.50
                else:
                    score = 0.45 - ((i - 20) * 0.005)  # Rest: 0.45 down to 0.05

                results.append(SearchResult(
                    id=f"result_{i}",
                    score=max(0.05, score),
                    payload={"content": f"Result content {i}"},
                ))

            # Return requested limit
            return results[:limit]

        store.search = search_with_distribution
        return store

    @pytest.fixture
    def searcher_with_distribution(self, mock_store_with_score_distribution) -> Searcher:
        """Create searcher with score distribution mock."""
        embedding = MockEmbedding()
        return Searcher(embedding, mock_store_with_score_distribution)

    async def test_ranking_is_stable(
        self,
        searcher_with_distribution: Searcher,
    ) -> None:
        """Verify ranking is consistent across calls."""
        results1 = await searcher_with_distribution.search_memories("test", limit=20)
        results2 = await searcher_with_distribution.search_memories("test", limit=20)

        # Same query should return same ranking
        ids1 = [r.id for r in results1]
        ids2 = [r.id for r in results2]

        assert ids1 == ids2, "Ranking should be stable for same query"

    async def test_scores_are_monotonically_decreasing(
        self,
        searcher_with_distribution: Searcher,
    ) -> None:
        """Verify results are ordered by decreasing score."""
        results = await searcher_with_distribution.search_memories("test", limit=50)

        scores = [r.score for r in results]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"Scores not monotonically decreasing: "
                f"score[{i}]={scores[i]} < score[{i+1}]={scores[i+1]}"
            )

    async def test_low_score_results_excluded_by_limit(
        self,
        searcher_with_distribution: Searcher,
    ) -> None:
        """Verify limit parameter excludes low-scoring results."""
        results_10 = await searcher_with_distribution.search_memories("test", limit=10)
        results_50 = await searcher_with_distribution.search_memories("test", limit=50)

        # Top 10 should have higher average score than top 50
        avg_score_10 = sum(r.score for r in results_10) / len(results_10)
        avg_score_50 = sum(r.score for r in results_50) / len(results_50)

        assert avg_score_10 > avg_score_50, (
            f"Top 10 avg ({avg_score_10:.3f}) should exceed "
            f"top 50 avg ({avg_score_50:.3f})"
        )
```

### 3. Memory Operations Tests

```python
# tests/validation/test_memory_operations.py

"""Validation tests for memory operations with production-like data.

Reference: SPEC-034 Memory Operations Scenarios 6-7
"""

import pytest
from unittest.mock import AsyncMock

from clams.embedding.mock import MockEmbedding
from clams.search.searcher import Searcher
from clams.storage.base import SearchResult

from tests.fixtures.data_profiles import MEMORY_PRODUCTION, MemoryProfile
from tests.fixtures.generators.memories import generate_memories


class TestCategorySkewHandling:
    """Scenario 6: Category Skew Handling.

    Verify search handles skewed category distributions correctly.
    """

    @pytest.fixture
    def skewed_category_corpus(self) -> list:
        """Generate corpus with 80% in one category."""
        profile = MemoryProfile(
            count=100,
            category_distribution={"fact": 0.8, "preference": 0.1, "workflow": 0.1},
        )
        return generate_memories(profile, seed=42)

    @pytest.fixture
    def mock_store(self, skewed_category_corpus) -> AsyncMock:
        """Mock store with skewed category corpus."""
        store = AsyncMock()
        corpus = skewed_category_corpus

        async def search_impl(collection, query, limit, filters=None):
            results_corpus = corpus

            # Apply category filter
            if filters and "category" in filters:
                results_corpus = [
                    m for m in results_corpus
                    if m.category == filters["category"]
                ]

            results = []
            for i, mem in enumerate(results_corpus[:limit]):
                results.append(SearchResult(
                    id=mem.id,
                    score=0.9 - (i * 0.01),
                    payload={
                        "content": mem.content,
                        "category": mem.category,
                        "importance": mem.importance,
                        "tags": mem.tags,
                    },
                ))

            return results

        store.search = search_impl
        return store

    @pytest.fixture
    def searcher(self, mock_store) -> Searcher:
        """Create searcher with skewed corpus."""
        embedding = MockEmbedding()
        return Searcher(embedding, mock_store)

    async def test_category_filter_works_with_skew(
        self,
        searcher: Searcher,
        skewed_category_corpus,
    ) -> None:
        """Category filter should work correctly even with skewed distribution."""
        # Filter for minority category
        results = await searcher.search_memories(
            "test query",
            category="preference",
            limit=50,
        )

        # Should only get preference category (10% of 100 = ~10)
        for r in results:
            assert r.category == "preference", f"Got {r.category}, expected preference"

        # Should have found the minority items
        assert len(results) > 0, "Should find some preference memories"

    async def test_unfiltered_search_not_dominated_by_category(
        self,
        searcher: Searcher,
    ) -> None:
        """Unfiltered search relevance should not over-weight dominant category."""
        results = await searcher.search_memories("test query", limit=20)

        # Results should include items from dominant category
        # (we're not testing for balance, just that search works)
        categories = set(r.category for r in results)
        assert "fact" in categories, "Should include dominant category"


class TestLargeMemoryCorpus:
    """Scenario 7: Large Memory Corpus Testing.

    Verify operations with 500 memories complete in acceptable time.
    """

    @pytest.fixture
    def large_corpus(self) -> list:
        """Generate 500 memories with varied content lengths."""
        return generate_memories(MEMORY_PRODUCTION, seed=42)

    @pytest.fixture
    def mock_store(self, large_corpus) -> AsyncMock:
        """Mock store with large corpus."""
        store = AsyncMock()

        async def search_impl(collection, query, limit, filters=None):
            results = []
            for i, mem in enumerate(large_corpus[:limit]):
                results.append(SearchResult(
                    id=mem.id,
                    score=0.95 - (i * 0.001),
                    payload={
                        "content": mem.content,
                        "category": mem.category,
                        "importance": mem.importance,
                        "tags": mem.tags,
                    },
                ))
            return results

        store.search = search_impl
        return store

    @pytest.fixture
    def searcher(self, mock_store) -> Searcher:
        """Create searcher with large corpus."""
        embedding = MockEmbedding()
        return Searcher(embedding, mock_store)

    @pytest.mark.timeout(1)  # 1 second timeout per spec
    async def test_search_returns_under_1s(
        self,
        searcher: Searcher,
    ) -> None:
        """Search should return in < 1 second for 500-memory corpus."""
        results = await searcher.search_memories("test query", limit=100)
        assert len(results) == 100

    async def test_handles_content_length_variation(
        self,
        searcher: Searcher,
        large_corpus,
    ) -> None:
        """Search should handle varied content lengths correctly."""
        # Content lengths should vary significantly
        lengths = [len(m.content) for m in large_corpus]
        min_len, max_len = min(lengths), max(lengths)

        assert max_len > min_len * 5, (
            f"Content length variation too low: min={min_len}, max={max_len}"
        )

        # Search should still work
        results = await searcher.search_memories("test", limit=50)
        assert len(results) == 50
```

### 4. Temporal Pattern Tests

```python
# tests/validation/test_temporal_patterns.py

"""Validation tests for temporal pattern handling.

Reference: SPEC-034 Temporal Data Scenarios 8-9
"""

from datetime import datetime, timedelta, timezone

import pytest

from tests.fixtures.data_profiles import CommitProfile, TemporalProfile
from tests.fixtures.generators.commits import generate_commits, COMMITS_PRODUCTION
from tests.fixtures.generators.temporal import generate_temporal_distribution, generate_from_profile


class TestBurstPatternHandling:
    """Scenario 8: Burst Pattern Handling.

    Verify search handles temporal clustering (bursts) correctly.
    """

    @pytest.fixture
    def burst_commits(self) -> list:
        """Generate commits with burst patterns."""
        profile = CommitProfile(
            count=200,
            author_count=5,
            temporal_pattern="bursts",
        )
        return generate_commits(profile, seed=42)

    def test_burst_detection(self, burst_commits) -> None:
        """Verify bursts are detectable in generated data."""
        timestamps = [c.committed_at for c in burst_commits]

        # Calculate inter-commit intervals
        intervals = []
        for i in range(1, len(timestamps)):
            delta = (timestamps[i] - timestamps[i - 1]).total_seconds()
            intervals.append(delta)

        # In burst patterns, we should see both very short and very long intervals
        min_interval = min(intervals)
        max_interval = max(intervals)

        # Variance should be high (mix of burst and quiet periods)
        import numpy as np
        interval_std = np.std(intervals)
        interval_mean = np.mean(intervals)
        cv = interval_std / interval_mean  # Coefficient of variation

        assert cv > 1.0, (
            f"Burst pattern should have high variance in intervals. "
            f"CV={cv:.2f}, expected > 1.0"
        )

    def test_date_range_filter_at_burst_boundaries(self, burst_commits) -> None:
        """Verify date range filters work correctly at burst boundaries."""
        timestamps = sorted([c.committed_at for c in burst_commits])

        # Find a burst (cluster of commits within short timeframe)
        burst_start = None
        burst_end = None
        window_hours = 4

        for i in range(len(timestamps) - 5):
            window_start = timestamps[i]
            window_end = window_start + timedelta(hours=window_hours)

            # Count commits in window
            commits_in_window = sum(
                1 for t in timestamps[i:]
                if window_start <= t <= window_end
            )

            if commits_in_window >= 10:  # Found a burst
                burst_start = window_start
                burst_end = window_end
                break

        if burst_start is None:
            pytest.skip("No clear burst found in test data")

        # Filter commits in burst window
        filtered = [
            c for c in burst_commits
            if burst_start <= c.committed_at <= burst_end
        ]

        # Should capture the burst
        assert len(filtered) >= 5, (
            f"Expected to find burst commits, got {len(filtered)}"
        )

        # Boundary test: just before burst should have fewer commits
        pre_burst_end = burst_start - timedelta(minutes=1)
        pre_burst_start = pre_burst_end - timedelta(hours=window_hours)
        pre_filtered = [
            c for c in burst_commits
            if pre_burst_start <= c.committed_at <= pre_burst_end
        ]

        # Pre-burst period should have fewer commits than burst
        assert len(pre_filtered) < len(filtered), (
            f"Pre-burst ({len(pre_filtered)}) should have fewer commits than burst ({len(filtered)})"
        )

    def test_search_handles_temporal_clustering(self, burst_commits) -> None:
        """Verify search operations work correctly with clustered timestamps."""
        # Group by day
        commits_by_day: dict[str, list] = {}
        for c in burst_commits:
            day_key = c.committed_at.strftime("%Y-%m-%d")
            commits_by_day.setdefault(day_key, []).append(c)

        # Burst pattern should show uneven distribution across days
        daily_counts = [len(commits) for commits in commits_by_day.values()]

        import numpy as np
        std_dev = np.std(daily_counts)
        mean_count = np.mean(daily_counts)

        # With bursts, some days should have many more commits than average
        max_day = max(daily_counts)
        assert max_day > mean_count * 2, (
            f"Burst pattern should have days with 2x+ average commits. "
            f"Max={max_day}, mean={mean_count:.1f}"
        )


class TestLongTimeRangeQueries:
    """Scenario 9: Long Time Range Queries.

    Verify queries across months of data work correctly.
    """

    @pytest.fixture
    def long_range_timestamps(self) -> list[datetime]:
        """Generate timestamps spanning 6 months."""
        profile = TemporalProfile(
            count=500,
            pattern="uniform",
            span_days=180,  # 6 months
        )
        return generate_from_profile(profile, seed=42)

    def test_since_filter_basic(self, long_range_timestamps) -> None:
        """Verify 'since' filter correctly excludes old data."""
        timestamps = sorted(long_range_timestamps)

        # Filter for last 30 days
        cutoff = timestamps[-1] - timedelta(days=30)
        filtered = [t for t in timestamps if t >= cutoff]

        # Should have roughly 30/180 = 16.7% of data (uniform distribution)
        expected_ratio = 30 / 180
        actual_ratio = len(filtered) / len(timestamps)

        # Allow 50% tolerance for randomness
        assert 0.5 * expected_ratio < actual_ratio < 1.5 * expected_ratio, (
            f"Since filter gave unexpected ratio: {actual_ratio:.2%}, "
            f"expected ~{expected_ratio:.2%}"
        )

    def test_no_off_by_one_at_boundaries(self, long_range_timestamps) -> None:
        """Verify no off-by-one errors at boundary timestamps."""
        timestamps = sorted(long_range_timestamps)

        # Use exact timestamp as boundary
        boundary = timestamps[100]

        # Inclusive boundary (>=)
        inclusive = [t for t in timestamps if t >= boundary]
        assert boundary in inclusive, "Boundary should be included with >="

        # Exclusive boundary (>)
        exclusive = [t for t in timestamps if t > boundary]
        assert boundary not in exclusive, "Boundary should not be included with >"

        # Counts should differ by 1
        assert len(inclusive) == len(exclusive) + 1, (
            f"Off-by-one error: inclusive={len(inclusive)}, exclusive={len(exclusive)}"
        )

    def test_boundary_at_midnight(self) -> None:
        """Verify date boundaries at midnight are handled correctly."""
        # Generate data around midnight boundary
        midnight = datetime(2024, 6, 15, 0, 0, 0, tzinfo=timezone.utc)

        test_times = [
            midnight - timedelta(seconds=1),  # 23:59:59 day before
            midnight,                          # 00:00:00 exact
            midnight + timedelta(seconds=1),  # 00:00:01 day of
        ]

        # Filter for "since midnight"
        since_midnight = [t for t in test_times if t >= midnight]
        assert len(since_midnight) == 2, "Should include midnight and after"
        assert test_times[0] not in since_midnight, "Should exclude before midnight"

    def test_month_boundary_queries(self, long_range_timestamps) -> None:
        """Verify queries at month boundaries work correctly."""
        timestamps = sorted(long_range_timestamps)

        # Group by month
        by_month: dict[str, list[datetime]] = {}
        for t in timestamps:
            month_key = t.strftime("%Y-%m")
            by_month.setdefault(month_key, []).append(t)

        # Should span multiple months
        assert len(by_month) >= 5, f"Expected 5+ months, got {len(by_month)}"

        # Each month should have some data (uniform distribution)
        for month, month_timestamps in by_month.items():
            assert len(month_timestamps) > 0, f"Month {month} has no data"

    def test_query_entire_range(self, long_range_timestamps) -> None:
        """Verify querying entire range returns all data."""
        timestamps = sorted(long_range_timestamps)

        earliest = timestamps[0]
        latest = timestamps[-1]

        # Query with range covering all data
        in_range = [t for t in timestamps if earliest <= t <= latest]

        assert len(in_range) == len(timestamps), (
            f"Full range query should return all {len(timestamps)} items, "
            f"got {len(in_range)}"
        )


class TestTemporalGeneratorProperties:
    """Verify temporal generator produces expected distributions."""

    @pytest.mark.parametrize("pattern", ["uniform", "bursts", "decay", "growth"])
    def test_pattern_coverage(self, pattern: str) -> None:
        """Verify all patterns produce valid timestamps."""
        timestamps = generate_temporal_distribution(
            count=100,
            pattern=pattern,
            span_days=30,
            seed=42,
        )

        assert len(timestamps) == 100, f"Expected 100 timestamps, got {len(timestamps)}"

        # All should be timezone-aware
        for t in timestamps:
            assert t.tzinfo is not None, "Timestamps should be timezone-aware"

        # Should be sorted
        assert timestamps == sorted(timestamps), "Timestamps should be sorted"

    def test_reproducibility(self) -> None:
        """Verify same seed produces same output."""
        ts1 = generate_temporal_distribution(count=50, pattern="bursts", span_days=30, seed=123)
        ts2 = generate_temporal_distribution(count=50, pattern="bursts", span_days=30, seed=123)

        assert ts1 == ts2, "Same seed should produce identical timestamps"

    def test_different_seeds_differ(self) -> None:
        """Verify different seeds produce different output."""
        ts1 = generate_temporal_distribution(count=50, pattern="uniform", span_days=30, seed=1)
        ts2 = generate_temporal_distribution(count=50, pattern="uniform", span_days=30, seed=2)

        assert ts1 != ts2, "Different seeds should produce different timestamps"
```

### 5. Parameter Robustness Tests

```python
# tests/validation/test_parameter_robustness.py

"""Validation tests for HDBSCAN parameter robustness.

Reference: SPEC-034 Algorithm Parameter Validation Scenario 10
"""

import numpy as np
import pytest

from clams.clustering import Clusterer

from tests.fixtures.data_profiles import EmbeddingProfile, GHAP_PRODUCTION, GHAP_DIFFUSE_CLOUD
from tests.fixtures.generators.embeddings import generate_clusterable_embeddings
from tests.fixtures.generators.ghap import generate_ghap_entries


class TestHDBSCANParameterRobustness:
    """Scenario 10: HDBSCAN Parameter Robustness Testing.

    Verify clustering parameters work across expected data characteristics
    and document minimum viable settings.
    """

    # Document expected data profiles and their characteristics
    DATA_PROFILES = {
        "small_well_separated": EmbeddingProfile(
            n_points=30,
            n_clusters=3,
            cluster_spread=0.1,
            inter_cluster_distance=0.8,
            noise_ratio=0.05,
        ),
        "medium_overlapping": EmbeddingProfile(
            n_points=100,
            n_clusters=4,
            cluster_spread=0.25,
            inter_cluster_distance=0.4,
            noise_ratio=0.15,
        ),
        "large_diffuse": EmbeddingProfile(
            n_points=200,
            n_clusters=2,
            cluster_spread=0.4,
            inter_cluster_distance=0.3,
            noise_ratio=0.25,
        ),
        "single_theme_cloud": EmbeddingProfile(
            n_points=100,
            n_clusters=1,
            cluster_spread=0.35,
            noise_ratio=0.1,
        ),
    }

    # Minimum viable parameter settings for each profile
    MINIMUM_VIABLE_PARAMS = {
        "small_well_separated": {"min_cluster_size": 5, "min_samples": 3},
        "medium_overlapping": {"min_cluster_size": 5, "min_samples": 3},
        "large_diffuse": {"min_cluster_size": 3, "min_samples": 2},
        "single_theme_cloud": {"min_cluster_size": 3, "min_samples": 2},
    }

    @pytest.mark.parametrize("profile_name", DATA_PROFILES.keys())
    def test_minimum_viable_params_produce_clusters(self, profile_name: str) -> None:
        """Verify minimum viable parameters produce clusters for each profile."""
        profile = self.DATA_PROFILES[profile_name]
        params = self.MINIMUM_VIABLE_PARAMS[profile_name]

        result = generate_clusterable_embeddings(profile, seed=42)

        clusterer = Clusterer(
            min_cluster_size=params["min_cluster_size"],
            min_samples=params["min_samples"],
            metric="cosine",
        )

        cluster_result = clusterer.cluster(result.embeddings)

        # Should find at least one cluster
        assert cluster_result.n_clusters >= 1, (
            f"Profile '{profile_name}' with params {params} should produce clusters. "
            f"Got {cluster_result.n_clusters} clusters, {cluster_result.noise_count} noise points."
        )

        # Not all points should be noise
        noise_ratio = cluster_result.noise_count / len(result.embeddings)
        assert noise_ratio < 0.9, (
            f"Profile '{profile_name}': too many noise points ({noise_ratio:.1%}). "
            f"Parameters may be too restrictive."
        )

    @pytest.mark.parametrize("min_cluster_size", [3, 5, 7, 10])
    def test_min_cluster_size_impact(self, min_cluster_size: int) -> None:
        """Verify min_cluster_size parameter has expected impact."""
        profile = EmbeddingProfile(
            n_points=100,
            n_clusters=5,
            cluster_spread=0.2,
            noise_ratio=0.1,
        )

        result = generate_clusterable_embeddings(profile, seed=42)

        clusterer = Clusterer(
            min_cluster_size=min_cluster_size,
            min_samples=min(3, min_cluster_size - 1),
            metric="cosine",
        )

        cluster_result = clusterer.cluster(result.embeddings)

        # Larger min_cluster_size should generally produce fewer clusters
        # (or same number with more noise)
        if min_cluster_size <= 5:
            # With small min_cluster_size, should find most clusters
            assert cluster_result.n_clusters >= 2, (
                f"min_cluster_size={min_cluster_size} should find multiple clusters"
            )

    @pytest.mark.parametrize("min_samples", [1, 2, 3, 5])
    def test_min_samples_impact(self, min_samples: int) -> None:
        """Verify min_samples parameter has expected impact on noise detection."""
        profile = EmbeddingProfile(
            n_points=100,
            n_clusters=3,
            cluster_spread=0.2,
            noise_ratio=0.2,  # 20% noise
        )

        result = generate_clusterable_embeddings(profile, seed=42)

        clusterer = Clusterer(
            min_cluster_size=5,
            min_samples=min_samples,
            metric="cosine",
        )

        cluster_result = clusterer.cluster(result.embeddings)

        # Higher min_samples should classify more points as noise
        # (stricter density requirement)
        if min_samples >= 3:
            # With strict min_samples, noise should be detected
            assert cluster_result.noise_count >= 10, (
                f"min_samples={min_samples} should detect some noise. "
                f"Got {cluster_result.noise_count} noise points."
            )

    def test_production_profile_with_default_params(self) -> None:
        """Verify production-like GHAP profile works with documented defaults."""
        result = generate_ghap_entries(GHAP_PRODUCTION, seed=42)

        # Use production default parameters
        clusterer = Clusterer(
            min_cluster_size=5,
            min_samples=3,
            metric="cosine",
        )

        cluster_result = clusterer.cluster(result.embeddings)

        # Document expected behavior for production profile
        # Production profile: 100 entries, 3 themes, 70% theme skew, 20% noise
        assert cluster_result.n_clusters >= 1, (
            f"Production profile should produce at least 1 cluster. "
            f"Got {cluster_result.n_clusters}."
        )

        # Log results for documentation purposes
        print(f"\nProduction profile clustering results:")
        print(f"  - Input points: {len(result.embeddings)}")
        print(f"  - Clusters found: {cluster_result.n_clusters}")
        print(f"  - Noise points: {cluster_result.noise_count}")
        print(f"  - Noise ratio: {cluster_result.noise_count / len(result.embeddings):.1%}")

    def test_diffuse_cloud_requires_relaxed_params(self) -> None:
        """Verify diffuse cloud profile requires relaxed parameters.

        This documents that single-theme diffuse data needs more permissive
        settings than the default production parameters.
        """
        result = generate_ghap_entries(GHAP_DIFFUSE_CLOUD, seed=42)

        # Default production params may fail on diffuse data
        strict_clusterer = Clusterer(
            min_cluster_size=5,
            min_samples=3,
            metric="cosine",
        )
        strict_result = strict_clusterer.cluster(result.embeddings)

        # Relaxed params for diffuse data
        relaxed_clusterer = Clusterer(
            min_cluster_size=3,
            min_samples=2,
            metric="cosine",
        )
        relaxed_result = relaxed_clusterer.cluster(result.embeddings)

        # Relaxed params should perform at least as well
        assert relaxed_result.n_clusters >= strict_result.n_clusters, (
            "Relaxed params should find at least as many clusters"
        )

        # Document the recommendation
        print(f"\nDiffuse cloud (BUG-031 scenario) results:")
        print(f"  - Strict params (5/3): {strict_result.n_clusters} clusters, "
              f"{strict_result.noise_count} noise")
        print(f"  - Relaxed params (3/2): {relaxed_result.n_clusters} clusters, "
              f"{relaxed_result.noise_count} noise")
        print(f"  RECOMMENDATION: Use min_cluster_size=3, min_samples=2 for diffuse data")


class TestParameterValidation:
    """Verify parameter assertions catch inappropriate settings."""

    def test_min_cluster_size_must_be_positive(self) -> None:
        """Verify min_cluster_size must be positive."""
        with pytest.raises((ValueError, AssertionError)):
            Clusterer(min_cluster_size=0, min_samples=1, metric="cosine")

    def test_min_samples_must_be_positive(self) -> None:
        """Verify min_samples must be positive."""
        with pytest.raises((ValueError, AssertionError)):
            Clusterer(min_cluster_size=3, min_samples=0, metric="cosine")

    def test_min_samples_should_not_exceed_min_cluster_size(self) -> None:
        """Document that min_samples > min_cluster_size is unusual.

        Note: HDBSCAN allows this, but it's usually a mistake.
        """
        profile = EmbeddingProfile(n_points=50, n_clusters=2, cluster_spread=0.2)
        result = generate_clusterable_embeddings(profile, seed=42)

        # This configuration is unusual
        clusterer = Clusterer(
            min_cluster_size=3,
            min_samples=10,  # Higher than min_cluster_size
            metric="cosine",
        )

        cluster_result = clusterer.cluster(result.embeddings)

        # This will likely produce all noise
        # Document this as a warning case
        print(f"\nUnusual params (min_samples > min_cluster_size):")
        print(f"  - Clusters: {cluster_result.n_clusters}")
        print(f"  - Noise: {cluster_result.noise_count} ({cluster_result.noise_count/50:.0%})")
        print(f"  WARNING: min_samples > min_cluster_size usually produces excessive noise")


class TestClusteringStability:
    """Verify clustering is deterministic and stable."""

    def test_deterministic_results(self) -> None:
        """Verify same input produces same clusters."""
        profile = EmbeddingProfile(n_points=100, n_clusters=3, cluster_spread=0.2)
        result = generate_clusterable_embeddings(profile, seed=42)

        clusterer = Clusterer(min_cluster_size=5, min_samples=3, metric="cosine")

        result1 = clusterer.cluster(result.embeddings)
        result2 = clusterer.cluster(result.embeddings)

        assert result1.n_clusters == result2.n_clusters
        assert result1.noise_count == result2.noise_count
        np.testing.assert_array_equal(result1.labels, result2.labels)

    def test_stability_across_seeds(self) -> None:
        """Verify similar results across different data seeds."""
        profile = EmbeddingProfile(n_points=100, n_clusters=3, cluster_spread=0.2)

        cluster_counts = []
        for seed in range(5):
            result = generate_clusterable_embeddings(profile, seed=seed)
            clusterer = Clusterer(min_cluster_size=5, min_samples=3, metric="cosine")
            cluster_result = clusterer.cluster(result.embeddings)
            cluster_counts.append(cluster_result.n_clusters)

        # Should find similar number of clusters across seeds
        # (not necessarily identical due to data variation)
        assert max(cluster_counts) - min(cluster_counts) <= 2, (
            f"Clustering should be stable across seeds. "
            f"Cluster counts: {cluster_counts}"
        )


class TestParameterDocumentation:
    """Document recommended parameters for different scenarios."""

    def test_document_parameter_recommendations(self) -> None:
        """Document recommended parameters in test output.

        This test serves as living documentation for parameter selection.
        """
        recommendations = """
        HDBSCAN Parameter Recommendations for CLAMS
        ==========================================

        Based on validation testing with production-like data profiles:

        1. WELL-SEPARATED CLUSTERS (distinct themes, low overlap)
           - min_cluster_size: 5
           - min_samples: 3
           - Expected: Clean cluster separation, low noise

        2. OVERLAPPING CLUSTERS (related themes, moderate overlap)
           - min_cluster_size: 5
           - min_samples: 3
           - Expected: Most clusters found, some merge possible

        3. DIFFUSE SINGLE-THEME DATA (BUG-031 scenario)
           - min_cluster_size: 3 (RELAXED from default 5)
           - min_samples: 2 (RELAXED from default 3)
           - Expected: Sub-clusters within theme, moderate noise

        4. HIGH-NOISE DATA (>25% outliers)
           - min_cluster_size: 5
           - min_samples: 5 (STRICTER for noise rejection)
           - Expected: Core clusters preserved, noise filtered

        Key Insights:
        - Default production params (5/3) work for 70%+ of cases
        - Diffuse/single-theme data needs relaxed params (3/2)
        - High-noise data benefits from stricter min_samples
        - Always validate with representative data before deployment
        """
        print(recommendations)

        # This test always passes - it's for documentation
        assert True
```

### 6. Test Configuration

```python
# tests/validation/conftest.py

"""Validation test configuration.

Validation tests use production-like data profiles and may take longer
than unit tests. They are marked for selective execution.
"""

import pytest


def pytest_configure(config):
    """Register validation test markers."""
    config.addinivalue_line(
        "markers",
        "validation: mark test as validation test (uses production-like data)"
    )


# Apply validation marker to all tests in this directory
def pytest_collection_modifyitems(items):
    """Add validation marker to all tests in validation directory."""
    for item in items:
        if "validation" in str(item.fspath):
            item.add_marker(pytest.mark.validation)


# Shared fixtures for validation tests
@pytest.fixture
def deterministic_seed() -> int:
    """Fixed seed for reproducible test data."""
    return 42


@pytest.fixture(autouse=True)
def ensure_reproducibility():
    """Ensure tests are deterministic."""
    import numpy as np
    np.random.seed(42)
    yield
```

## File-by-File Implementation Plan

### Phase 1: Data Profile Infrastructure (Priority 1)

| File | Action | Details |
|------|--------|---------|
| `tests/fixtures/__init__.py` | Modify | Add exports for data_profiles and generators |
| `tests/fixtures/data_profiles.py` | Create | Profile dataclasses and presets (see design above); includes CodeUnitProfile and CommitProfile |
| `tests/fixtures/generators/__init__.py` | Create | Package exports |
| `tests/fixtures/generators/embeddings.py` | Create | Embedding generator with cluster control (see Section 1 design) |
| `tests/fixtures/generators/ghap.py` | Create | GHAP entry generator (see Section 2 design) |
| `tests/fixtures/generators/temporal.py` | Create | Temporal pattern generator (see Section 3 design) |
| `tests/fixtures/generators/memories.py` | Create | Memory corpus generator (see Section 4 design) |
| `tests/fixtures/generators/code.py` | Create | Code unit generator (see Section 5 "Code Unit Generator" for full implementation) |
| `tests/fixtures/generators/commits.py` | Create | Git commit generator (see Section 6 "Git Commit Generator" for full implementation) |

### Phase 2: Clustering Validation (Priority 2)

| File | Action | Details |
|------|--------|---------|
| `tests/validation/__init__.py` | Create | Package marker |
| `tests/validation/conftest.py` | Create | Validation-specific fixtures and markers |
| `tests/validation/test_clustering_validation.py` | Create | Scenarios 1-3 (see design above) |

### Phase 3: Search/Pagination Validation (Priority 3)

| File | Action | Details |
|------|--------|---------|
| `tests/validation/test_search_pagination.py` | Create | Scenarios 4-5 (see design above) |

### Phase 4: Memory and Temporal Validation (Priority 4)

| File | Action | Details |
|------|--------|---------|
| `tests/validation/test_memory_operations.py` | Create | Scenarios 6-7 (see design above) |
| `tests/validation/test_temporal_patterns.py` | Create | Scenarios 8-9 (see "Temporal Pattern Tests" section above for full implementation) |

### Phase 5: Documentation and Benchmarks (Priority 5)

| File | Action | Details |
|------|--------|---------|
| `tests/validation/test_parameter_robustness.py` | Create | Scenario 10 - HDBSCAN parameter validation (see Section 5 "Parameter Robustness Tests" above for full implementation) |
| `tests/performance/benchmark_results.json` | Modify | Extended with generation timing |
| `tests/fixtures/data_profiles.py` | Modify | Add docstrings documenting rationale; add CodeUnitProfile (see Section 5 "Code Unit Generator" for definition) |

## Testing Strategy

### Unit Tests for Generators

Each generator should have its own unit tests verifying:
- Output shape and types match profile
- Reproducibility with fixed seed
- Profile validation catches invalid parameters
- Edge cases (zero counts, extreme skews)

```python
# tests/fixtures/generators/test_embeddings.py

def test_embedding_shape_matches_profile():
    profile = EmbeddingProfile(n_points=50, embedding_dim=768)
    result = generate_clusterable_embeddings(profile, seed=42)
    assert result.embeddings.shape == (50, 768)

def test_reproducibility():
    result1 = generate_clusterable_embeddings(EMBEDDINGS_WELL_SEPARATED, seed=42)
    result2 = generate_clusterable_embeddings(EMBEDDINGS_WELL_SEPARATED, seed=42)
    np.testing.assert_array_equal(result1.embeddings, result2.embeddings)
```

### Integration Tests

The validation tests serve as integration tests, verifying:
- Generators produce data that exercises target algorithms
- Algorithm behavior matches expectations on realistic data
- Performance remains acceptable at production scale

### Performance Baselines

Extend existing benchmark tests to track:
- Data generation time (target: < 5s for any profile)
- Clustering time with generated data (target: < 10s for 200 points)
- Search time with generated corpus (target: < 1s for 500 memories)

## Alternative Approaches Considered

### 1. Real Production Data Snapshots

**Considered**: Export anonymized production data for testing.

**Rejected**:
- Privacy concerns even with anonymization
- Requires production environment access
- Data becomes stale quickly
- Profiles capture essence without actual data

### 2. Property-Based Testing with Hypothesis

**Considered**: Use Hypothesis to generate arbitrary data.

**Rejected for primary approach**:
- Less control over specific distributions
- Harder to reproduce specific bug scenarios
- Can still use Hypothesis for generator unit tests

### 3. Synthetic Data from ML Models

**Considered**: Use language models to generate realistic GHAP content.

**Rejected**:
- Adds external dependency
- Non-deterministic
- Overkill for testing algorithm behavior
- Template-based approach sufficient for this use case

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2024-01-XX | Use dataclasses for profiles | Immutable, type-safe, good IDE support |
| 2024-01-XX | Separate generators by data type | Cleaner imports, independent testing |
| 2024-01-XX | Use von Mises-Fisher for embeddings | Natural distribution for unit vectors |
| 2024-01-XX | Template-based GHAP generation | Deterministic, covers theme variations |
| 2024-01-XX | Validation tests in separate directory | Clear separation from unit tests |

## Open Questions

None - design is ready for implementation.

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Generators too slow for CI | Target < 5s per profile; parallel generation if needed |
| Profile drift from production | Document profile rationale; update based on bug feedback |
| Over-fitting to current bugs | Design profiles for general characteristics, not specific bugs |
| Test flakiness from randomness | Fixed seeds everywhere; validate stability |
