"""GHAP entry generators for validation testing.

This module generates GHAP entries with realistic characteristics
for testing clustering and search algorithms.

Reference: SPEC-034 GHAP Generator Design
Reference: BUG-031 - Clustering failed with 63 similar GHAP entries
"""

import datetime
import uuid
from datetime import timedelta
from typing import NamedTuple

import numpy as np
import numpy.typing as npt

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
from tests.fixtures.data_profiles import EmbeddingProfile, GHAPDataProfile
from tests.fixtures.generators.embeddings import generate_clusterable_embeddings
from tests.fixtures.generators.temporal import generate_temporal_distribution


class GeneratedGHAPData(NamedTuple):
    """Result from GHAP generation."""

    entries: list[GHAPEntry]
    embeddings: npt.NDArray[np.float32]  # Full narrative embeddings
    theme_labels: npt.NDArray[np.int64]  # Which theme each entry belongs to


# Theme templates for generating realistic GHAP narratives
THEME_TEMPLATES: dict[str, dict[str, str]] = {
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

    outcomes_list: list[OutcomeStatus] = (
        [OutcomeStatus.CONFIRMED] * n_confirmed
        + [OutcomeStatus.FALSIFIED] * n_falsified
        + [OutcomeStatus.ABANDONED] * n_abandoned
    )
    rng.shuffle(outcomes_list)

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
        i for i, d in enumerate(domains) if d.value == profile.dominant_domain
    )
    domain_weights[dominant_idx] = profile.domain_concentration * len(domains)
    domain_weights = domain_weights / domain_weights.sum()
    domain_assignments = rng.choice(
        len(domains),
        size=profile.count,
        p=domain_weights,
    )

    entries: list[GHAPEntry] = []
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
            outcome=_generate_outcome(outcomes_list[i], timestamps[i], rng),
            surprise=(
                _generate_surprise(rng)
                if outcomes_list[i] == OutcomeStatus.FALSIFIED
                else None
            ),
            root_cause=(
                _generate_root_cause(rng)
                if outcomes_list[i] == OutcomeStatus.FALSIFIED
                else None
            ),
            lesson=(
                _generate_lesson(rng)
                if outcomes_list[i] != OutcomeStatus.ABANDONED
                else None
            ),
            confidence_tier=_get_confidence_tier(outcomes_list[i]),
        )
        entries.append(entry)

    # Generate embeddings that match theme structure
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
        "module": str(rng.choice(modules)),
        "component": str(rng.choice(components)),
        "condition": str(rng.choice(conditions)),
        "resource": str(rng.choice(resources)),
        "operation": str(rng.choice(operations)),
        "endpoint": str(rng.choice(endpoints)),
        "parameters": str(rng.choice(parameters)),
        "boundary": str(rng.choice(boundaries)),
        "target": str(rng.integers(80, 100)),
    }


def _generate_outcome(
    status: OutcomeStatus,
    timestamp: "datetime.datetime",
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
        captured_at=timestamp + timedelta(hours=int(rng.integers(1, 24))),
        auto_captured=bool(rng.integers(0, 2)),
    )


def _generate_surprise(rng: np.random.Generator) -> str:
    """Generate surprise text for falsified outcomes."""
    surprises = [
        "The actual cause was unrelated to initial hypothesis",
        "A side effect masked the real issue",
        "The problem was in a different layer than expected",
        "Test environment masked production behavior",
        "Race condition appeared only under load",
    ]
    return str(rng.choice(surprises))


def _generate_root_cause(rng: np.random.Generator) -> RootCause:
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
    idx = int(rng.integers(0, len(categories)))
    return RootCause(category=categories[idx], description=descriptions[idx])


def _generate_lesson(rng: np.random.Generator) -> Lesson:
    """Generate lesson learned."""
    lessons = [
        ("Check assumptions early", "Always validate assumptions before implementing"),
        ("Add logging first", "Logging helps narrow down issues faster"),
        ("Test edge cases", "Edge cases reveal hidden bugs"),
        ("Review dependencies", "Dependencies can have unexpected behaviors"),
    ]
    idx = int(rng.integers(0, len(lessons)))
    return Lesson(what_worked=lessons[idx][0], takeaway=lessons[idx][1])


def _get_confidence_tier(status: OutcomeStatus) -> ConfidenceTier:
    """Determine confidence tier based on outcome."""
    if status == OutcomeStatus.ABANDONED:
        return ConfidenceTier.ABANDONED
    elif status == OutcomeStatus.CONFIRMED:
        return ConfidenceTier.GOLD
    else:
        return ConfidenceTier.SILVER
