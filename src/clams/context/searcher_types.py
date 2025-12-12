"""Type definitions for Searcher interface (used by ContextAssembler).

This module re-exports result types from clams.search.results for use
by the ContextAssembler and provides the abstract Searcher interface.
"""

from abc import ABC, abstractmethod

# Re-export result types from canonical source
from clams.search.results import (
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
        self, query: str, limit: int = 20
    ) -> list[MemoryResult]:
        """
        Search memories by semantic similarity.

        Args:
            query: Natural language query
            limit: Maximum results to return

        Returns:
            List of memory results sorted by relevance
        """
        pass

    @abstractmethod
    async def search_code(
        self, query: str, limit: int = 20
    ) -> list[CodeResult]:
        """
        Search code units by semantic similarity.

        Args:
            query: Natural language query
            limit: Maximum results to return

        Returns:
            List of code results sorted by relevance
        """
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
    ) -> list[ExperienceResult]:
        """
        Search experiences by semantic similarity.

        Args:
            query: Natural language query
            axis: Which axis to search ("full", "strategy", "surprise", "root_cause")
            domain: Optional domain filter
            strategy: Optional strategy filter
            outcome: Optional outcome status filter
            limit: Maximum results to return

        Returns:
            List of experience results sorted by relevance
        """
        pass

    @abstractmethod
    async def search_values(
        self, query: str, limit: int = 5
    ) -> list[ValueResult]:
        """
        Search values by semantic similarity.

        Args:
            query: Natural language query
            limit: Maximum results to return

        Returns:
            List of value results sorted by relevance
        """
        pass

    @abstractmethod
    async def search_commits(
        self, query: str, limit: int = 20
    ) -> list[CommitResult]:
        """
        Search commits by semantic similarity.

        Args:
            query: Natural language query
            limit: Maximum results to return

        Returns:
            List of commit results sorted by relevance
        """
        pass
