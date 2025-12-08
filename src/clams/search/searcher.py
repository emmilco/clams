"""Unified query interface for semantic search."""

from datetime import datetime
from typing import Any

from clams.embedding.base import EmbeddingService
from clams.storage.base import VectorStore

from .collections import CollectionName, InvalidAxisError
from .results import (
    CodeResult,
    CommitResult,
    ExperienceResult,
    MemoryResult,
    ValueResult,
)


class SearchError(Exception):
    """Base exception for search operations."""

    pass


class InvalidSearchModeError(SearchError):
    """Raised when an invalid search mode is specified."""

    pass


class CollectionNotFoundError(SearchError):
    """Raised when a collection doesn't exist."""

    pass


class EmbeddingError(SearchError):
    """Raised when query embedding fails."""

    pass


def _build_filters(**kwargs: Any) -> dict[str, Any] | None:
    """Build VectorStore filter dict from keyword arguments.

    Args:
        **kwargs: Filter parameters (None values are ignored)

    Returns:
        Filter dict or None if no filters specified

    Note:
        Currently only supports simple equality and $gte (date range) operators.
        Advanced operators like $in, $lte are not yet supported by the Qdrant
        implementation and will be added in a future version.
    """
    filters: dict[str, Any] = {}
    for key, value in kwargs.items():
        if value is not None:
            if isinstance(value, datetime):
                # Date filters use $gte operator with timestamp
                filters[key] = {"$gte": value.timestamp()}
            else:
                # Simple equality filter
                filters[key] = value

    return filters if filters else None


class Searcher:
    """Unified query interface across all vector collections."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
    ):
        """Initialize searcher with dependencies.

        Args:
            embedding_service: Service for embedding query text
            vector_store: Vector storage backend
        """
        self._embedding_service = embedding_service
        self._vector_store = vector_store

    async def search_memories(
        self,
        query: str,
        category: str | None = None,
        limit: int = 10,
        search_mode: str = "semantic",
    ) -> list[MemoryResult]:
        """Search verified memory entries.

        Args:
            query: Search query text
            category: Optional filter by memory category
            limit: Maximum results to return
            search_mode: Search mode (semantic, keyword, hybrid). Default: semantic.

        Returns:
            List of memory search results ordered by relevance

        Raises:
            InvalidSearchModeError: If search_mode is not "semantic"
            EmbeddingError: If query embedding fails
            CollectionNotFoundError: If memories collection doesn't exist
        """
        # Handle empty query
        if not query or not query.strip():
            return []

        # Validate search mode (only semantic supported in v1)
        if search_mode != "semantic":
            raise InvalidSearchModeError(
                f"Invalid search mode '{search_mode}'. "
                "Only 'semantic' mode is currently supported. "
                "Hybrid search will be added in a future release."
            )

        try:
            # Generate embedding
            query_vector = await self._embedding_service.embed(query)
        except Exception as e:
            raise EmbeddingError(f"Failed to embed query: {e}") from e

        # Build filters
        filters = _build_filters(category=category)

        try:
            # Search
            results = await self._vector_store.search(
                collection=CollectionName.MEMORIES,
                query=query_vector,
                limit=limit,
                filters=filters,
            )
        except Exception as e:
            # Check if collection doesn't exist
            if "collection not found" in str(e).lower():
                raise CollectionNotFoundError(
                    f"Collection '{CollectionName.MEMORIES}' not found. "
                    "Ensure memories have been indexed."
                ) from e
            # Other VectorStore errors propagate
            raise

        # Map results
        return [MemoryResult.from_search_result(r) for r in results]

    async def search_code(
        self,
        query: str,
        project: str | None = None,
        language: str | None = None,
        unit_type: str | None = None,
        limit: int = 10,
        search_mode: str = "semantic",
    ) -> list[CodeResult]:
        """Search indexed code units.

        Args:
            query: Search query text
            project: Optional filter by project name
            language: Optional filter by programming language
            unit_type: Optional filter by unit type (function, class, method)
            limit: Maximum results to return
            search_mode: Search mode (semantic, keyword, hybrid). Default: semantic.

        Returns:
            List of code search results ordered by relevance

        Raises:
            InvalidSearchModeError: If search_mode is not "semantic"
            EmbeddingError: If query embedding fails
            CollectionNotFoundError: If code collection doesn't exist
        """
        # Handle empty query
        if not query or not query.strip():
            return []

        # Validate search mode (only semantic supported in v1)
        if search_mode != "semantic":
            raise InvalidSearchModeError(
                f"Invalid search mode '{search_mode}'. "
                "Only 'semantic' mode is currently supported. "
                "Hybrid search will be added in a future release."
            )

        try:
            # Generate embedding
            query_vector = await self._embedding_service.embed(query)
        except Exception as e:
            raise EmbeddingError(f"Failed to embed query: {e}") from e

        # Build filters
        filters = _build_filters(
            project=project,
            language=language,
            unit_type=unit_type,
        )

        try:
            # Search
            results = await self._vector_store.search(
                collection=CollectionName.CODE,
                query=query_vector,
                limit=limit,
                filters=filters,
            )
        except Exception as e:
            # Check if collection doesn't exist
            if "collection not found" in str(e).lower():
                raise CollectionNotFoundError(
                    f"Collection '{CollectionName.CODE}' not found. "
                    "Ensure code has been indexed."
                ) from e
            # Other VectorStore errors propagate
            raise

        # Map results
        return [CodeResult.from_search_result(r) for r in results]

    async def search_experiences(
        self,
        query: str,
        axis: str = "full",
        domain: str | None = None,
        strategy: str | None = None,
        outcome: str | None = None,
        limit: int = 10,
        search_mode: str = "semantic",
    ) -> list[ExperienceResult]:
        """Search GHAP experiences across clustering axes.

        Args:
            query: Search query text
            axis: Clustering axis (full, strategy, surprise, root_cause)
            domain: Optional filter by domain (metadata filter on experiences_full)
            strategy: Optional filter by strategy (metadata filter on experiences_strategy)
            outcome: Optional filter by outcome status (confirmed, falsified, abandoned)
            limit: Maximum results to return
            search_mode: Search mode (semantic, keyword, hybrid). Default: semantic.

        Returns:
            List of experience search results ordered by relevance

        Raises:
            InvalidAxisError: If axis is not valid
            InvalidSearchModeError: If search_mode is not "semantic"
            EmbeddingError: If query embedding fails
            CollectionNotFoundError: If experience collection doesn't exist
        """
        # Handle empty query
        if not query or not query.strip():
            return []

        # Validate search mode (only semantic supported in v1)
        if search_mode != "semantic":
            raise InvalidSearchModeError(
                f"Invalid search mode '{search_mode}'. "
                "Only 'semantic' mode is currently supported. "
                "Hybrid search will be added in a future release."
            )

        try:
            # Get collection name (validates axis)
            collection = CollectionName.get_experience_collection(axis)
        except InvalidAxisError:
            # Re-raise with no wrapping (already has good message)
            raise

        try:
            # Generate embedding
            query_vector = await self._embedding_service.embed(query)
        except Exception as e:
            raise EmbeddingError(f"Failed to embed query: {e}") from e

        # Build filters
        filters = _build_filters(domain=domain, strategy=strategy, outcome_status=outcome)

        try:
            # Search
            results = await self._vector_store.search(
                collection=collection,
                query=query_vector,
                limit=limit,
                filters=filters,
            )
        except Exception as e:
            # Check if collection doesn't exist
            if "collection not found" in str(e).lower():
                raise CollectionNotFoundError(
                    f"Collection '{collection}' not found. "
                    "Ensure experiences have been indexed."
                ) from e
            # Other VectorStore errors propagate
            raise

        # Map results
        return [ExperienceResult.from_search_result(r) for r in results]

    async def search_values(
        self,
        query: str,
        axis: str | None = None,
        limit: int = 5,
        search_mode: str = "semantic",
    ) -> list[ValueResult]:
        """Search emergent values.

        Args:
            query: Search query text
            axis: Optional filter by axis (strategy, surprise, root_cause)
            limit: Maximum results to return (default 5, values are sparse)
            search_mode: Search mode (semantic, keyword, hybrid). Default: semantic.

        Returns:
            List of value search results ordered by relevance

        Raises:
            InvalidSearchModeError: If search_mode is not "semantic"
            EmbeddingError: If query embedding fails
            CollectionNotFoundError: If values collection doesn't exist
        """
        # Handle empty query
        if not query or not query.strip():
            return []

        # Validate search mode (only semantic supported in v1)
        if search_mode != "semantic":
            raise InvalidSearchModeError(
                f"Invalid search mode '{search_mode}'. "
                "Only 'semantic' mode is currently supported. "
                "Hybrid search will be added in a future release."
            )

        try:
            # Generate embedding
            query_vector = await self._embedding_service.embed(query)
        except Exception as e:
            raise EmbeddingError(f"Failed to embed query: {e}") from e

        # Build filters
        filters = _build_filters(axis=axis)

        try:
            # Search
            results = await self._vector_store.search(
                collection=CollectionName.VALUES,
                query=query_vector,
                limit=limit,
                filters=filters,
            )
        except Exception as e:
            # Check if collection doesn't exist
            if "collection not found" in str(e).lower():
                raise CollectionNotFoundError(
                    f"Collection '{CollectionName.VALUES}' not found. "
                    "Ensure values have been indexed."
                ) from e
            # Other VectorStore errors propagate
            raise

        # Map results
        return [ValueResult.from_search_result(r) for r in results]

    async def search_commits(
        self,
        query: str,
        author: str | None = None,
        since: datetime | None = None,
        limit: int = 10,
        search_mode: str = "semantic",
    ) -> list[CommitResult]:
        """Search git commit messages and diffs.

        Args:
            query: Search query text
            author: Optional filter by commit author
            since: Optional filter by minimum commit date
            limit: Maximum results to return
            search_mode: Search mode (semantic, keyword, hybrid). Default: semantic.

        Returns:
            List of commit search results ordered by relevance

        Raises:
            InvalidSearchModeError: If search_mode is not "semantic"
            EmbeddingError: If query embedding fails
            CollectionNotFoundError: If commits collection doesn't exist
        """
        # Handle empty query
        if not query or not query.strip():
            return []

        # Validate search mode (only semantic supported in v1)
        if search_mode != "semantic":
            raise InvalidSearchModeError(
                f"Invalid search mode '{search_mode}'. "
                "Only 'semantic' mode is currently supported. "
                "Hybrid search will be added in a future release."
            )

        try:
            # Generate embedding
            query_vector = await self._embedding_service.embed(query)
        except Exception as e:
            raise EmbeddingError(f"Failed to embed query: {e}") from e

        # Build filters
        filters = _build_filters(author=author, committed_at=since)

        try:
            # Search
            results = await self._vector_store.search(
                collection=CollectionName.COMMITS,
                query=query_vector,
                limit=limit,
                filters=filters,
            )
        except Exception as e:
            # Check if collection doesn't exist
            if "collection not found" in str(e).lower():
                raise CollectionNotFoundError(
                    f"Collection '{CollectionName.COMMITS}' not found. "
                    "Ensure commits have been indexed."
                ) from e
            # Other VectorStore errors propagate
            raise

        # Map results
        return [CommitResult.from_search_result(r) for r in results]
