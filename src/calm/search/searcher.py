"""Unified query interface for semantic search."""

from datetime import datetime
from typing import Any

from calm.context.searcher_types import Searcher as SearcherABC
from calm.embedding.base import EmbeddingService
from calm.storage.base import VectorStore

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
    """Build VectorStore filter dict from keyword arguments."""
    filters: dict[str, Any] = {}
    for key, value in kwargs.items():
        if value is not None:
            if isinstance(value, datetime):
                filters[key] = {"$gte": value.timestamp()}
            else:
                filters[key] = value

    return filters if filters else None


class Searcher(SearcherABC):
    """Unified query interface across all vector collections."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
    ):
        self._embedding_service = embedding_service
        self._vector_store = vector_store

    async def search_memories(
        self,
        query: str,
        category: str | None = None,
        limit: int = 10,
        search_mode: str = "semantic",
    ) -> list[MemoryResult]:
        if not query or not query.strip():
            return []

        if search_mode != "semantic":
            raise InvalidSearchModeError(
                f"Invalid search mode '{search_mode}'. "
                "Only 'semantic' mode is currently supported."
            )

        try:
            query_vector = await self._embedding_service.embed(query)
        except Exception as e:
            raise EmbeddingError(f"Failed to embed query: {e}") from e

        filters = _build_filters(category=category)

        try:
            results = await self._vector_store.search(
                collection=CollectionName.MEMORIES,
                query=query_vector,
                limit=limit,
                filters=filters,
            )
        except Exception as e:
            if "collection not found" in str(e).lower():
                raise CollectionNotFoundError(
                    f"Collection '{CollectionName.MEMORIES}' not found."
                ) from e
            raise

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
        if not query or not query.strip():
            return []

        if search_mode != "semantic":
            raise InvalidSearchModeError(
                f"Invalid search mode '{search_mode}'. "
                "Only 'semantic' mode is currently supported."
            )

        try:
            query_vector = await self._embedding_service.embed(query)
        except Exception as e:
            raise EmbeddingError(f"Failed to embed query: {e}") from e

        filters = _build_filters(
            project=project,
            language=language,
            unit_type=unit_type,
        )

        try:
            results = await self._vector_store.search(
                collection=CollectionName.CODE,
                query=query_vector,
                limit=limit,
                filters=filters,
            )
        except Exception as e:
            if "collection not found" in str(e).lower():
                raise CollectionNotFoundError(
                    f"Collection '{CollectionName.CODE}' not found."
                ) from e
            raise

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
        if not query or not query.strip():
            return []

        if search_mode != "semantic":
            raise InvalidSearchModeError(
                f"Invalid search mode '{search_mode}'. "
                "Only 'semantic' mode is currently supported."
            )

        try:
            collection = CollectionName.get_experience_collection(axis)
        except InvalidAxisError:
            raise

        try:
            query_vector = await self._embedding_service.embed(query)
        except Exception as e:
            raise EmbeddingError(f"Failed to embed query: {e}") from e

        filters = _build_filters(
            domain=domain, strategy=strategy, outcome_status=outcome
        )

        try:
            results = await self._vector_store.search(
                collection=collection,
                query=query_vector,
                limit=limit,
                filters=filters,
            )
        except Exception as e:
            if "collection not found" in str(e).lower():
                raise CollectionNotFoundError(
                    f"Collection '{collection}' not found."
                ) from e
            raise

        return [ExperienceResult.from_search_result(r) for r in results]

    async def search_values(
        self,
        query: str,
        axis: str | None = None,
        limit: int = 5,
        search_mode: str = "semantic",
    ) -> list[ValueResult]:
        if not query or not query.strip():
            return []

        if search_mode != "semantic":
            raise InvalidSearchModeError(
                f"Invalid search mode '{search_mode}'. "
                "Only 'semantic' mode is currently supported."
            )

        try:
            query_vector = await self._embedding_service.embed(query)
        except Exception as e:
            raise EmbeddingError(f"Failed to embed query: {e}") from e

        filters = _build_filters(axis=axis)

        try:
            results = await self._vector_store.search(
                collection=CollectionName.VALUES,
                query=query_vector,
                limit=limit,
                filters=filters,
            )
        except Exception as e:
            if "collection not found" in str(e).lower():
                raise CollectionNotFoundError(
                    f"Collection '{CollectionName.VALUES}' not found."
                ) from e
            raise

        return [ValueResult.from_search_result(r) for r in results]

    async def search_commits(
        self,
        query: str,
        author: str | None = None,
        since: datetime | None = None,
        limit: int = 10,
        search_mode: str = "semantic",
    ) -> list[CommitResult]:
        if not query or not query.strip():
            return []

        if search_mode != "semantic":
            raise InvalidSearchModeError(
                f"Invalid search mode '{search_mode}'. "
                "Only 'semantic' mode is currently supported."
            )

        try:
            query_vector = await self._embedding_service.embed(query)
        except Exception as e:
            raise EmbeddingError(f"Failed to embed query: {e}") from e

        filters = _build_filters(author=author, committed_at=since)

        try:
            results = await self._vector_store.search(
                collection=CollectionName.COMMITS,
                query=query_vector,
                limit=limit,
                filters=filters,
            )
        except Exception as e:
            if "collection not found" in str(e).lower():
                raise CollectionNotFoundError(
                    f"Collection '{CollectionName.COMMITS}' not found."
                ) from e
            raise

        return [CommitResult.from_search_result(r) for r in results]
