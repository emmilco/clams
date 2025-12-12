"""Type definitions for Searcher interface (used by ContextAssembler).

This module re-exports result types from clams.search.results for use
by the ContextAssembler and provides the abstract Searcher interface.
"""

from abc import ABC, abstractmethod
from datetime import datetime

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
    """Abstract searcher interface for querying all sources.

    This abstract base class defines the interface for semantic search across
    various data sources. The concrete implementation in `clams.search.searcher`
    inherits from this ABC.

    All methods accept optional filter parameters with defaults, allowing callers
    to use a minimal interface (just query and limit) while implementations can
    support richer filtering.
    """

    @abstractmethod
    async def search_memories(
        self,
        query: str,
        category: str | None = None,
        limit: int = 20,
        search_mode: str = "semantic",
    ) -> list[MemoryResult]:
        """
        Search memories by semantic similarity.

        Args:
            query: Natural language query
            category: Optional filter by memory category
            limit: Maximum results to return
            search_mode: Search mode (semantic, keyword, hybrid). Default: semantic.

        Returns:
            List of memory results sorted by relevance
        """
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
        """
        Search code units by semantic similarity.

        Args:
            query: Natural language query
            project: Optional filter by project name
            language: Optional filter by programming language
            unit_type: Optional filter by unit type (function, class, method)
            limit: Maximum results to return
            search_mode: Search mode (semantic, keyword, hybrid). Default: semantic.

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
        search_mode: str = "semantic",
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
            search_mode: Search mode (semantic, keyword, hybrid). Default: semantic.

        Returns:
            List of experience results sorted by relevance
        """
        pass

    @abstractmethod
    async def search_values(
        self,
        query: str,
        axis: str | None = None,
        limit: int = 5,
        search_mode: str = "semantic",
    ) -> list[ValueResult]:
        """
        Search values by semantic similarity.

        Args:
            query: Natural language query
            axis: Optional filter by axis (strategy, surprise, root_cause)
            limit: Maximum results to return
            search_mode: Search mode (semantic, keyword, hybrid). Default: semantic.

        Returns:
            List of value results sorted by relevance
        """
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
        """
        Search commits by semantic similarity.

        Args:
            query: Natural language query
            author: Optional filter by commit author
            since: Optional filter by minimum commit date
            limit: Maximum results to return
            search_mode: Search mode (semantic, keyword, hybrid). Default: semantic.

        Returns:
            List of commit results sorted by relevance
        """
        pass
