"""Unified query interface for semantic, keyword, and hybrid search."""

from datetime import datetime
from typing import Any

from calm.context.searcher_types import Searcher as SearcherABC
from calm.embedding.base import EmbeddingService
from calm.storage.base import SearchResult, VectorStore

from .collections import CollectionName, InvalidAxisError
from .results import (
    CodeResult,
    CommitResult,
    ExperienceResult,
    MemoryResult,
    ValueResult,
)

# Valid search modes
VALID_SEARCH_MODES = ("semantic", "keyword", "hybrid")

# Maximum number of items to scroll through for keyword search.
# This caps memory usage for keyword-mode collection scans.
_KEYWORD_SCROLL_LIMIT = 1000

# Text payload fields to search per collection.
# Each mapping is collection_name -> list of payload field names that
# contain user-visible text worth matching against.
_TEXT_FIELDS: dict[str, list[str]] = {
    CollectionName.MEMORIES: ["content"],
    CollectionName.CODE_UNITS: ["code", "qualified_name", "docstring"],
    CollectionName.COMMITS: ["message"],
    CollectionName.VALUES: ["text"],
    CollectionName.EXPERIENCES_FULL: [
        "goal",
        "hypothesis",
        "action",
        "prediction",
        "outcome_result",
    ],
    CollectionName.EXPERIENCES_STRATEGY: [
        "goal",
        "hypothesis",
        "action",
        "prediction",
        "outcome_result",
    ],
    CollectionName.EXPERIENCES_SURPRISE: [
        "goal",
        "hypothesis",
        "action",
        "prediction",
        "outcome_result",
        "surprise",
    ],
    CollectionName.EXPERIENCES_ROOT_CAUSE: [
        "goal",
        "hypothesis",
        "action",
        "prediction",
        "outcome_result",
    ],
}

# Hybrid mode boost for keyword matches.  When a result appears in both
# semantic and keyword results, its semantic score is boosted by this amount.
_HYBRID_KEYWORD_BOOST = 0.15


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


def _validate_search_mode(mode: str) -> None:
    """Validate that search_mode is one of the allowed values.

    Args:
        mode: The search mode to validate.

    Raises:
        InvalidSearchModeError: If mode is not in VALID_SEARCH_MODES.
    """
    if mode not in VALID_SEARCH_MODES:
        valid = ", ".join(f"'{m}'" for m in VALID_SEARCH_MODES)
        raise InvalidSearchModeError(
            f"Invalid search mode '{mode}'. Must be one of: {valid}"
        )


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


def _keyword_match_score(
    query: str, payload: dict[str, Any], text_fields: list[str]
) -> float:
    """Compute a keyword relevance score for a single payload.

    The score is between 0.0 and 1.0.  An exact full-field match scores 1.0.
    A substring match scores proportionally based on how many of the query
    terms appear and the ratio of query length to field length.

    Args:
        query: The user's search query (already lowercased).
        payload: The payload dict of a stored vector.
        text_fields: Which payload keys to examine.

    Returns:
        A float between 0.0 (no match) and 1.0 (perfect match).
    """
    best_score = 0.0
    query_lower = query.lower()
    query_terms = query_lower.split()

    for field in text_fields:
        value = payload.get(field)
        if not value or not isinstance(value, str):
            continue
        value_lower = value.lower()

        # Exact full match
        if query_lower == value_lower:
            return 1.0

        # Full query substring match
        if query_lower in value_lower:
            # Score proportional to how much of the field the query covers
            ratio = len(query_lower) / max(len(value_lower), 1)
            score = 0.6 + 0.4 * ratio  # range [0.6, 1.0)
            best_score = max(best_score, score)
            continue

        # Term-level matching: count how many query terms appear
        if query_terms:
            matched_terms = sum(1 for t in query_terms if t in value_lower)
            if matched_terms > 0:
                term_ratio = matched_terms / len(query_terms)
                score = 0.3 * term_ratio
                best_score = max(best_score, score)

    return best_score


async def _keyword_search(
    vector_store: VectorStore,
    collection: str,
    query: str,
    limit: int,
    filters: dict[str, Any] | None,
    text_fields: list[str],
) -> list[SearchResult]:
    """Perform keyword (text substring) search over a collection.

    Scrolls through the collection, filters by text match, and returns
    the top results sorted by keyword relevance score.

    Args:
        vector_store: The vector store to search.
        collection: Collection name.
        query: User's text query.
        limit: Maximum results to return.
        filters: Optional payload filters (category, project, etc.).
        text_fields: Payload field names to search for text matches.

    Returns:
        List of SearchResult with score set to keyword relevance.
    """
    # Fetch candidates from the collection (with metadata filters applied)
    try:
        candidates = await vector_store.scroll(
            collection=collection,
            limit=_KEYWORD_SCROLL_LIMIT,
            filters=filters,
            with_vectors=False,
        )
    except Exception as e:
        if "collection not found" in str(e).lower():
            raise CollectionNotFoundError(
                f"Collection '{collection}' not found."
            ) from e
        raise

    # Score each candidate by keyword match
    scored: list[tuple[float, SearchResult]] = []
    for result in candidates:
        score = _keyword_match_score(query, result.payload, text_fields)
        if score > 0.0:
            scored.append((
                score,
                SearchResult(
                    id=result.id,
                    score=score,
                    payload=result.payload,
                    vector=None,
                ),
            ))

    # Sort by score descending, then take top `limit`
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:limit]]


async def _semantic_search(
    embedding_service: EmbeddingService,
    vector_store: VectorStore,
    collection: str,
    query: str,
    limit: int,
    filters: dict[str, Any] | None,
) -> list[SearchResult]:
    """Perform semantic (vector similarity) search.

    Args:
        embedding_service: Service to embed the query text.
        vector_store: The vector store to search.
        collection: Collection name.
        query: User's text query.
        limit: Maximum results to return.
        filters: Optional payload filters.

    Returns:
        List of SearchResult ordered by semantic similarity.

    Raises:
        EmbeddingError: If query embedding fails.
        CollectionNotFoundError: If the collection does not exist.
    """
    try:
        query_vector = await embedding_service.embed(query)
    except Exception as e:
        raise EmbeddingError(f"Failed to embed query: {e}") from e

    try:
        return await vector_store.search(
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


async def _hybrid_search(
    embedding_service: EmbeddingService,
    vector_store: VectorStore,
    collection: str,
    query: str,
    limit: int,
    filters: dict[str, Any] | None,
    text_fields: list[str],
) -> list[SearchResult]:
    """Perform hybrid search (semantic + keyword with boost).

    Runs semantic search first, then keyword search.  Results from both
    are merged: keyword-only results are appended with their keyword score,
    while results that appear in both get a boost to their semantic score.

    Args:
        embedding_service: Service to embed the query text.
        vector_store: The vector store to search.
        collection: Collection name.
        query: User's text query.
        limit: Maximum results to return.
        filters: Optional payload filters.
        text_fields: Payload field names to search for text matches.

    Returns:
        Merged and re-ranked list of SearchResult.
    """
    # Run semantic search (get extra results for merging headroom)
    semantic_results = await _semantic_search(
        embedding_service, vector_store, collection, query, limit, filters
    )

    # Run keyword search
    keyword_results = await _keyword_search(
        vector_store, collection, query, limit, filters, text_fields
    )

    # Build lookup of keyword scores by ID
    keyword_scores: dict[str, float] = {
        r.id: r.score for r in keyword_results
    }

    # Merge: start with semantic results, boosting those with keyword matches
    merged: dict[str, SearchResult] = {}
    for r in semantic_results:
        boosted_score = r.score
        if r.id in keyword_scores:
            boosted_score = min(r.score + _HYBRID_KEYWORD_BOOST, 1.0)
        merged[r.id] = SearchResult(
            id=r.id,
            score=boosted_score,
            payload=r.payload,
            vector=None,
        )

    # Add keyword-only results (not already in semantic results)
    for r in keyword_results:
        if r.id not in merged:
            merged[r.id] = r

    # Sort by final score descending, return top `limit`
    all_results = sorted(merged.values(), key=lambda x: x.score, reverse=True)
    return all_results[:limit]


class Searcher(SearcherABC):
    """Unified query interface across all vector collections.

    Supports three search modes:
        - ``"semantic"``: Vector similarity search (default).
        - ``"keyword"``: Case-insensitive text substring matching on
          payload fields.
        - ``"hybrid"``: Semantic search with keyword-match boosting.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
    ):
        self._embedding_service = embedding_service
        self._vector_store = vector_store

    # ------------------------------------------------------------------
    # Memories
    # ------------------------------------------------------------------

    async def search_memories(
        self,
        query: str,
        category: str | None = None,
        limit: int = 10,
        search_mode: str = "semantic",
    ) -> list[MemoryResult]:
        if not query or not query.strip():
            return []

        _validate_search_mode(search_mode)

        filters = _build_filters(category=category)
        collection = CollectionName.MEMORIES
        text_fields = _TEXT_FIELDS.get(collection, [])

        results = await self._dispatch_search(
            search_mode, collection, query, limit, filters, text_fields
        )
        return [MemoryResult.from_search_result(r) for r in results]

    # ------------------------------------------------------------------
    # Code
    # ------------------------------------------------------------------

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

        _validate_search_mode(search_mode)

        filters = _build_filters(
            project=project, language=language, unit_type=unit_type
        )
        collection = CollectionName.CODE_UNITS
        text_fields = _TEXT_FIELDS.get(collection, [])

        results = await self._dispatch_search(
            search_mode, collection, query, limit, filters, text_fields
        )
        return [CodeResult.from_search_result(r) for r in results]

    # ------------------------------------------------------------------
    # Experiences
    # ------------------------------------------------------------------

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

        _validate_search_mode(search_mode)

        try:
            collection = CollectionName.get_experience_collection(axis)
        except InvalidAxisError:
            raise

        filters = _build_filters(
            domain=domain, strategy=strategy, outcome_status=outcome
        )
        text_fields = _TEXT_FIELDS.get(collection, [])

        results = await self._dispatch_search(
            search_mode, collection, query, limit, filters, text_fields
        )
        return [ExperienceResult.from_search_result(r) for r in results]

    # ------------------------------------------------------------------
    # Values
    # ------------------------------------------------------------------

    async def search_values(
        self,
        query: str,
        axis: str | None = None,
        limit: int = 5,
        search_mode: str = "semantic",
    ) -> list[ValueResult]:
        if not query or not query.strip():
            return []

        _validate_search_mode(search_mode)

        filters = _build_filters(axis=axis)
        collection = CollectionName.VALUES
        text_fields = _TEXT_FIELDS.get(collection, [])

        results = await self._dispatch_search(
            search_mode, collection, query, limit, filters, text_fields
        )
        return [ValueResult.from_search_result(r) for r in results]

    # ------------------------------------------------------------------
    # Commits
    # ------------------------------------------------------------------

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

        _validate_search_mode(search_mode)

        filters = _build_filters(author=author, committed_at=since)
        collection = CollectionName.COMMITS
        text_fields = _TEXT_FIELDS.get(collection, [])

        results = await self._dispatch_search(
            search_mode, collection, query, limit, filters, text_fields
        )
        return [CommitResult.from_search_result(r) for r in results]

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    async def _dispatch_search(
        self,
        search_mode: str,
        collection: str,
        query: str,
        limit: int,
        filters: dict[str, Any] | None,
        text_fields: list[str],
    ) -> list[SearchResult]:
        """Route to the correct search strategy based on mode.

        Args:
            search_mode: One of "semantic", "keyword", "hybrid".
            collection: Vector store collection name.
            query: User's text query.
            limit: Maximum results.
            filters: Optional payload filters.
            text_fields: Payload fields used for keyword matching.

        Returns:
            List of SearchResult.
        """
        if search_mode == "semantic":
            return await _semantic_search(
                self._embedding_service,
                self._vector_store,
                collection,
                query,
                limit,
                filters,
            )
        elif search_mode == "keyword":
            return await _keyword_search(
                self._vector_store,
                collection,
                query,
                limit,
                filters,
                text_fields,
            )
        else:  # hybrid
            return await _hybrid_search(
                self._embedding_service,
                self._vector_store,
                collection,
                query,
                limit,
                filters,
                text_fields,
            )
