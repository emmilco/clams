"""Data generators for validation testing.

This package provides generators that produce realistic test data
matching production-like data profiles defined in data_profiles.py.

Reference: SPEC-034 - Parameter Validation with Production Data

Usage:
    from tests.fixtures.data_profiles import GHAP_PRODUCTION
    from tests.fixtures.generators import generate_ghap_entries

    result = generate_ghap_entries(GHAP_PRODUCTION, seed=42)
    entries = result.entries
    embeddings = result.embeddings
"""

from tests.fixtures.generators.code import GeneratedCodeUnit, generate_code_units
from tests.fixtures.generators.commits import GeneratedCommit, generate_commits
from tests.fixtures.generators.embeddings import (
    GeneratedEmbeddings,
    generate_clusterable_embeddings,
)
from tests.fixtures.generators.ghap import GeneratedGHAPData, generate_ghap_entries
from tests.fixtures.generators.memories import GeneratedMemory, generate_memories
from tests.fixtures.generators.temporal import (
    generate_from_profile,
    generate_temporal_distribution,
)

__all__ = [
    # Embedding generators
    "GeneratedEmbeddings",
    "generate_clusterable_embeddings",
    # GHAP generators
    "GeneratedGHAPData",
    "generate_ghap_entries",
    # Memory generators
    "GeneratedMemory",
    "generate_memories",
    # Temporal generators
    "generate_temporal_distribution",
    "generate_from_profile",
    # Code generators
    "GeneratedCodeUnit",
    "generate_code_units",
    # Commit generators
    "GeneratedCommit",
    "generate_commits",
]
