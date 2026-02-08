"""Unified query interface for semantic search."""

from .collections import CollectionName, InvalidAxisError
from .results import (
    CodeResult,
    CommitResult,
    ExperienceResult,
    Lesson,
    MemoryResult,
    RootCause,
    ValueResult,
)

# Note: Searcher and SearchError are not imported here to avoid circular import.
# Import them from calm.search.searcher directly.

__all__ = [
    "InvalidAxisError",
    "MemoryResult",
    "CodeResult",
    "ExperienceResult",
    "ValueResult",
    "CommitResult",
    "RootCause",
    "Lesson",
    "CollectionName",
]
