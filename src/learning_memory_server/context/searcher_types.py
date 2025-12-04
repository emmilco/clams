"""Type definitions for Searcher interface (used by ContextAssembler)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class MemoryResult:
    """Result from memory search."""

    id: str
    category: str
    content: str
    score: float
    importance: float
    tags: list[str]
    created_at: datetime
    verified_at: datetime | None
    verification_status: str | None


@dataclass
class CodeResult:
    """Result from code search."""

    id: str
    unit_type: str  # "function", "class", "method"
    qualified_name: str
    file_path: str
    start_line: int
    end_line: int
    language: str
    code: str
    docstring: str | None
    score: float


@dataclass
class ExperienceResult:
    """Result from experience search."""

    id: str
    ghap_id: str
    axis: str  # "full", "strategy", "surprise", "root_cause"
    domain: str
    strategy: str
    goal: str
    hypothesis: str
    action: str
    prediction: str
    outcome_status: str
    outcome_result: str
    surprise: str | None
    root_cause: str | None
    lesson: dict[str, Any] | None
    confidence_tier: str
    iteration_count: int
    score: float
    created_at: datetime


@dataclass
class ValueResult:
    """Result from value search."""

    id: str
    axis: str
    cluster_id: str
    cluster_size: int
    text: str
    similarity_to_centroid: float
    score: float


@dataclass
class CommitResult:
    """Result from commit search."""

    id: str
    sha: str
    author: str
    committed_at: str
    message: str
    files_changed: list[str]
    insertions: int
    deletions: int
    score: float


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
