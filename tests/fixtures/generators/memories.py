"""Memory corpus generators for validation testing.

This module generates memory entries with realistic characteristics
for testing search and retrieval operations.

Reference: SPEC-034 Memory Generator Design
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

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
        seed: Random seed for reproducibility

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
    importances: npt.NDArray[np.floating[Any]]
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
    content_templates: dict[str, list[str]] = {
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
        "python",
        "javascript",
        "testing",
        "debugging",
        "performance",
        "security",
        "api",
        "database",
        "frontend",
        "backend",
        "docker",
        "kubernetes",
        "ci-cd",
        "documentation",
        "refactoring",
    ]

    memories: list[GeneratedMemory] = []
    for i in range(profile.count):
        category = str(category_assignments[i])

        # Generate content from template
        template = str(rng.choice(content_templates.get(category, content_templates["fact"])))
        content = _fill_template(template, rng)

        # Adjust content length to be within range
        min_len, max_len = profile.content_length_range
        target_len = int(rng.integers(min_len, max_len + 1))
        content = _adjust_content_length(content, target_len, rng)

        # Generate tags
        min_tags, max_tags = profile.tag_count_range
        n_tags = int(rng.integers(min_tags, max_tags + 1))
        tags = rng.choice(
            all_tags, size=min(n_tags, len(all_tags)), replace=False
        ).tolist()

        # Generate deterministic ID from seed and index
        id_bytes = rng.bytes(6)
        deterministic_id = id_bytes.hex()

        memories.append(
            GeneratedMemory(
                id=f"mem_{deterministic_id}",
                content=content,
                category=category,
                importance=float(importances[i]),
                tags=[str(t) for t in tags],
            )
        )

    return memories


def _fill_template(template: str, rng: np.random.Generator) -> str:
    """Fill a template with random but plausible values."""
    fills: dict[str, str] = {
        "component": str(rng.choice(["auth", "cache", "queue", "validator", "parser"])),
        "algorithm": str(rng.choice(["HDBSCAN", "BFS", "binary search", "hash table"])),
        "purpose": str(rng.choice(["clustering", "indexing", "validation", "caching"])),
        "issue": str(
            rng.choice(["memory leak", "race condition", "timeout", "crash"])
        ),
        "location": str(
            rng.choice(["logs", "stack trace", "database queries", "network calls"])
        ),
        "Framework": str(rng.choice(["FastAPI", "SQLAlchemy", "PyTorch", "Pydantic"])),
        "version": f"{rng.integers(1, 5)}.{rng.integers(0, 20)}",
        "feature": str(
            rng.choice(["async support", "type hints", "new API", "performance boost"])
        ),
        "endpoint": str(rng.choice(["/api/v1/users", "/search", "/health", "/metrics"])),
        "auth_type": str(rng.choice(["Bearer token", "API key", "OAuth2", "Basic"])),
        "table": str(rng.choice(["users", "items", "logs", "sessions"])),
        "column": str(rng.choice(["created_at", "user_id", "status", "type"])),
        "style": str(rng.choice(["functional", "object-oriented", "declarative"])),
        "language": str(rng.choice(["Python", "TypeScript", "Go", "Rust"])),
        "tool": str(rng.choice(["pytest", "mypy", "ruff", "docker"])),
        "domain": str(rng.choice(["testing", "deployment", "debugging", "profiling"])),
        "approach": str(
            rng.choice(["composition", "dependency injection", "immutability"])
        ),
        "alternative": str(rng.choice(["inheritance", "global state", "mutability"])),
        "context": str(rng.choice(["new features", "refactoring", "bug fixes"])),
        "command": str(rng.choice(["pytest", "make build", "docker-compose up"])),
        "task": str(
            rng.choice(["feature development", "bug investigation", "code review"])
        ),
        "steps": str(rng.integers(3, 10)),
        "checklist": str(rng.choice(["tests", "types", "documentation", "security"])),
        "branch_pattern": str(rng.choice(["feature/", "bugfix/", "release/"])),
        "feature_type": str(rng.choice(["new features", "bug fixes", "releases"])),
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
        content += str(rng.choice(extensions))

    return content[:target_len]
