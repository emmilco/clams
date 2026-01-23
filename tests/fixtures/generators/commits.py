"""Git commit generators for validation testing.

This module generates git commit data for testing temporal
pattern handling and search operations.

Reference: SPEC-034 Git Commits table
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import numpy.typing as npt

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
COMMIT_TEMPLATES: dict[str, list[str]] = {
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
    type_weights = [
        0.35,
        0.25,
        0.15,
        0.10,
        0.10,
        0.05,
    ]  # feature, fix, refactor, docs, test, chore
    type_assignments = rng.choice(commit_types, size=profile.count, p=type_weights)

    commits: list[GeneratedCommit] = []
    for i in range(profile.count):
        author = authors[int(author_indices[i])]
        commit_type = str(type_assignments[i])

        # Generate message
        message = _generate_commit_message(commit_type, rng)

        # Generate files changed
        min_files, max_files = profile.files_per_commit_range
        n_files = int(rng.integers(min_files, max_files + 1))
        files_changed = _generate_file_list(n_files, rng)

        # Generate line changes (correlated with file count)
        avg_changes_per_file = int(rng.integers(5, 50))
        insertions = int(n_files * avg_changes_per_file * rng.uniform(0.5, 1.5))
        deletions = int(n_files * avg_changes_per_file * rng.uniform(0.2, 0.8))

        commits.append(
            GeneratedCommit(
                sha=uuid.uuid4().hex[:40],
                author_name=author["name"],
                author_email=author["email"],
                committed_at=timestamps[i],
                message=message,
                files_changed=files_changed,
                insertions=insertions,
                deletions=deletions,
            )
        )

    return commits


def _generate_author_pool(count: int, rng: np.random.Generator) -> list[dict[str, str]]:
    """Generate a pool of realistic author names and emails."""
    first_names = [
        "Alice",
        "Bob",
        "Charlie",
        "Diana",
        "Eve",
        "Frank",
        "Grace",
        "Henry",
        "Ivy",
        "Jack",
    ]
    last_names = [
        "Smith",
        "Johnson",
        "Williams",
        "Brown",
        "Jones",
        "Garcia",
        "Miller",
        "Davis",
        "Wilson",
        "Taylor",
    ]
    domains = ["example.com", "company.org", "dev.io"]

    authors: list[dict[str, str]] = []
    for i in range(count):
        first = str(rng.choice(first_names))
        last = str(rng.choice(last_names))
        domain = str(rng.choice(domains))
        authors.append(
            {
                "name": f"{first} {last}",
                "email": f"{first.lower()}.{last.lower()}@{domain}",
            }
        )

    return authors


def _generate_skewed_weights(
    count: int,
    skew: float,
    rng: np.random.Generator,
) -> npt.NDArray[np.floating[Any]]:
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

    result: npt.NDArray[np.floating[Any]] = weights / weights.sum()
    return result


def _generate_commit_message(commit_type: str, rng: np.random.Generator) -> str:
    """Generate a realistic commit message."""
    template = str(rng.choice(COMMIT_TEMPLATES[commit_type]))

    fills: dict[str, str] = {
        "component": str(
            rng.choice(
                ["auth", "api", "cache", "storage", "handler", "service", "client"]
            )
        ),
        "purpose": str(
            rng.choice(
                ["validation", "error handling", "performance", "security", "logging"]
            )
        ),
        "scope": str(rng.choice(["core", "api", "db", "auth", "utils"])),
        "feature": str(
            rng.choice(
                [
                    "user management",
                    "caching",
                    "rate limiting",
                    "retry logic",
                    "metrics",
                ]
            )
        ),
        "issue": str(
            rng.choice(
                [
                    "null pointer",
                    "race condition",
                    "memory leak",
                    "timeout",
                    "validation error",
                ]
            )
        ),
        "edge_case": str(
            rng.choice(
                [
                    "empty input",
                    "large payload",
                    "unicode characters",
                    "concurrent access",
                ]
            )
        ),
        "condition": str(
            rng.choice(
                [
                    "timeout occurs",
                    "input is empty",
                    "connection fails",
                    "cache misses",
                ]
            )
        ),
        "source": str(rng.choice(["monolith", "utils", "helpers", "base class"])),
        "topic": str(
            rng.choice(["installation", "configuration", "API usage", "deployment"])
        ),
        "task": str(
            rng.choice(["cleanup", "update configs", "bump versions", "reorganize"])
        ),
    }

    message = template.format(**fills)

    # Sometimes add body
    if rng.random() < 0.3:
        body = str(
            rng.choice(
                [
                    "\n\nThis change improves reliability.",
                    "\n\nPart of the ongoing refactoring effort.",
                    "\n\nAddresses feedback from code review.",
                    "\n\nRequired for the upcoming release.",
                ]
            )
        )
        message += body

    return message


def _generate_file_list(count: int, rng: np.random.Generator) -> list[str]:
    """Generate a list of changed file paths."""
    extensions = [".py", ".ts", ".go", ".json", ".yaml", ".md"]
    dirs = ["src", "lib", "tests", "config", "docs"]
    subdirs = ["auth", "api", "core", "utils", "models", "services"]
    filenames = [
        "index",
        "main",
        "utils",
        "helpers",
        "types",
        "config",
        "test_",
        "spec_",
    ]

    files: list[str] = []
    for _ in range(count):
        dir_path = str(rng.choice(dirs))
        if rng.random() < 0.7:  # Usually have subdirectory
            dir_path = f"{dir_path}/{rng.choice(subdirs)}"

        filename = str(rng.choice(filenames)) + str(rng.choice(["", "_v2", "_new"]))
        ext = str(rng.choice(extensions))

        files.append(f"{dir_path}/{filename}{ext}")

    return files
