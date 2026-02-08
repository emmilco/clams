"""Type definitions for Searcher interface (used by ContextAssembler).

Re-exports result types from calm.search.results for use
by the ContextAssembler and provides the abstract Searcher interface.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from calm.search.results import (
    CodeResult,
    CommitResult,
    ExperienceResult,
    Lesson,
    MemoryResult,
    RootCause,
    ValueResult,
)

__all__ = [
    "CodeResult",
    "CommitResult",
    "ExperienceResult",
    "Lesson",
    "MemoryResult",
    "RootCause",
    "Searcher",
    "ValueResult",
]


class Searcher(ABC):
    """Abstract searcher interface for querying all sources."""

    @abstractmethod
    async def search_memories(
        self,
        query: str,
        category: str | None = None,
        limit: int = 20,
        search_mode: str = "semantic",
    ) -> list[MemoryResult]:
        pass

    @abstractmethod
    async def search_code(
        self,
        query: str,
        project: str | None = None,
        language: str | None = None,
        unit_type: str | None = None,
        limit: int = 20,
        search_mode: str = "semantic",
    ) -> list[CodeResult]:
        pass

    @abstractmethod
    async def search_experiences(
        self,
        query: str,
        axis: str = "full",
        domain: str | None = None,
        strategy: str | None = None,
        outcome: str | None = None,
        limit: int = 20,
        search_mode: str = "semantic",
    ) -> list[ExperienceResult]:
        pass

    @abstractmethod
    async def search_values(
        self,
        query: str,
        axis: str | None = None,
        limit: int = 5,
        search_mode: str = "semantic",
    ) -> list[ValueResult]:
        pass

    @abstractmethod
    async def search_commits(
        self,
        query: str,
        author: str | None = None,
        since: datetime | None = None,
        limit: int = 20,
        search_mode: str = "semantic",
    ) -> list[CommitResult]:
        pass
