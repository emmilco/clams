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
from .searcher import (
    CollectionNotFoundError,
    EmbeddingError,
    InvalidSearchModeError,
    Searcher,
    SearchError,
)

__all__ = [
    "Searcher",
    "SearchError",
    "InvalidAxisError",
    "InvalidSearchModeError",
    "CollectionNotFoundError",
    "EmbeddingError",
    "MemoryResult",
    "CodeResult",
    "ExperienceResult",
    "ValueResult",
    "CommitResult",
    "RootCause",
    "Lesson",
    "CollectionName",
]
