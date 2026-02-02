"""Git analysis tools for CALM MCP server."""

from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import Any

import structlog

from calm.embedding.base import EmbeddingService
from calm.storage.base import VectorStore

from .errors import MCPError
from .validation import ValidationError, validate_query_string

logger = structlog.get_logger()

# Type alias for tool functions
ToolFunc = Callable[..., Coroutine[Any, Any, dict[str, Any]]]

# Track whether collection has been ensured
_commits_collection_ensured = False


def validate_author_name(author: str | None, max_length: int = 200) -> None:
    """Validate optional author name filter.

    Args:
        author: Author name or None
        max_length: Maximum allowed length

    Raises:
        ValidationError: If author is provided but too long
    """
    if author is None:
        return
    if len(author) > max_length:
        raise ValidationError(
            f"Author name too long ({len(author)} chars). "
            f"Maximum: {max_length} characters"
        )


async def _ensure_commits_collection(
    vector_store: VectorStore, semantic_embedder: EmbeddingService
) -> None:
    """Ensure commits collection exists (lazy initialization)."""
    global _commits_collection_ensured
    if _commits_collection_ensured:
        return

    try:
        await vector_store.create_collection(
            name="commits",
            dimension=semantic_embedder.dimension,
            distance="cosine",
        )
        logger.info("collection_created", name="commits")
    except Exception as e:
        error_msg = str(e).lower()
        if "already exists" in error_msg or "409" in str(e):
            logger.debug("collection_exists", name="commits")
        else:
            raise

    _commits_collection_ensured = True


def get_git_tools(
    vector_store: VectorStore,
    semantic_embedder: EmbeddingService,
) -> dict[str, ToolFunc]:
    """Get git tool implementations for the dispatcher.

    Args:
        vector_store: Initialized vector store
        semantic_embedder: Initialized semantic embedding service

    Returns:
        Dictionary mapping tool names to their implementations
    """

    async def index_commits(
        since: str | None = None,
        limit: int | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Index git commits for semantic search.

        This is a placeholder that returns a not-implemented response.
        Full indexing functionality requires git integration which
        is not yet ported to CALM.

        Args:
            since: Optional date filter (ISO format YYYY-MM-DD)
            limit: Optional max commits to index (default: all from last 5 years)
            force: Force reindex all commits (default: false, incremental)

        Returns:
            Status indicating feature is not yet available
        """
        logger.info("git.index_commits", since=since, limit=limit, force=force)

        # Validate since date if provided
        if since:
            try:
                datetime.fromisoformat(since)
            except ValueError as e:
                raise ValidationError(
                    f"Invalid date format '{since}'. Use ISO format: YYYY-MM-DD"
                ) from e

        # Validate limit if provided
        if limit is not None:
            if limit < 1:
                raise ValidationError(f"Limit must be positive, got {limit}")
            if limit > 100_000:
                raise ValidationError(f"Limit {limit} exceeds maximum of 100000")

        # For now, return a placeholder response
        return {
            "status": "not_implemented",
            "message": (
                "Git commit indexing is not yet available in CALM. "
                "This feature requires git integration which will be "
                "ported in a future release."
            ),
        }

    async def search_commits(
        query: str,
        author: str | None = None,
        since: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Search git commits semantically.

        Args:
            query: Search query
            author: Optional author name filter
            since: Optional date filter (ISO format YYYY-MM-DD)
            limit: Max results (1-50, default 10)

        Returns:
            Matching commits with scores
        """
        logger.info("git.search_commits", query=query[:50], author=author)

        # Ensure collection exists
        await _ensure_commits_collection(vector_store, semantic_embedder)

        # Validate limit
        if not 1 <= limit <= 50:
            raise ValidationError(
                f"Limit {limit} out of range. Must be between 1 and 50."
            )

        # Validate query length
        validate_query_string(query)

        # Validate author name if provided
        validate_author_name(author)

        # Parse date if provided
        since_dt = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since)
            except ValueError as e:
                raise ValidationError(
                    f"Invalid date format '{since}'. Use ISO format: YYYY-MM-DD"
                ) from e

        # Handle empty query
        if not query.strip():
            return {"results": [], "count": 0}

        try:
            # Generate query embedding
            query_embedding = await semantic_embedder.embed(query)

            # Build filters
            filters: dict[str, Any] = {}
            if author:
                filters["author"] = author
            if since_dt:
                filters["committed_at"] = {"$gte": since_dt.timestamp()}

            # Search
            results = await vector_store.search(
                collection="commits",
                query=query_embedding,
                limit=limit,
                filters=filters if filters else None,
            )

            # Format results
            formatted = []
            for result in results:
                # Convert timestamp to ISO format if present
                committed_at = result.payload.get("committed_at")
                if isinstance(committed_at, (int, float)):
                    committed_at = datetime.fromtimestamp(committed_at).isoformat()

                formatted.append(
                    {
                        "sha": result.payload.get("sha", result.id),
                        "message": result.payload.get("message", ""),
                        "author": result.payload.get("author", ""),
                        "author_email": result.payload.get("author_email", ""),
                        "timestamp": committed_at,
                        "files_changed": result.payload.get("files_changed", []),
                        "file_count": len(result.payload.get("files_changed", [])),
                        "insertions": result.payload.get("insertions", 0),
                        "deletions": result.payload.get("deletions", 0),
                        "score": result.score,
                    }
                )

            logger.info("git.commits_found", count=len(formatted))

            return {"results": formatted, "count": len(formatted)}

        except Exception as e:
            error_msg = str(e).lower()
            if "not found" in error_msg or "404" in str(e):
                # Collection doesn't exist or is empty
                logger.info("git.collection_empty")
                return {"results": [], "count": 0}
            logger.error("git.search_commits_failed", error=str(e), exc_info=True)
            raise MCPError(f"Failed to search commits: {e}") from e

    async def get_file_history(
        path: str,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Get commit history for a specific file.

        This is a placeholder that returns a not-implemented response.
        Full functionality requires git integration.

        Args:
            path: File path relative to repo root
            limit: Max commits (1-500, default 100)

        Returns:
            Status indicating feature is not yet available
        """
        logger.info("git.file_history", path=path, limit=limit)

        # Validate limit
        if not 1 <= limit <= 500:
            raise ValidationError(
                f"Limit {limit} out of range. Must be between 1 and 500."
            )

        # For now, return a placeholder response
        return {
            "status": "not_implemented",
            "message": (
                "Git file history is not yet available in CALM. "
                "This feature requires git integration which will be "
                "ported in a future release."
            ),
            "path": path,
        }

    async def get_churn_hotspots(
        days: int = 90,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Find files with highest change frequency.

        This is a placeholder that returns a not-implemented response.
        Full functionality requires git integration.

        Args:
            days: Analysis window in days (1-365, default 90)
            limit: Max results (1-50, default 10)

        Returns:
            Status indicating feature is not yet available
        """
        logger.info("git.churn_hotspots", days=days, limit=limit)

        # Validate parameters
        if not 1 <= days <= 365:
            raise ValidationError(
                f"Days {days} out of range. Must be between 1 and 365."
            )
        if not 1 <= limit <= 50:
            raise ValidationError(
                f"Limit {limit} out of range. Must be between 1 and 50."
            )

        # For now, return a placeholder response
        return {
            "status": "not_implemented",
            "message": (
                "Git churn analysis is not yet available in CALM. "
                "This feature requires git integration which will be "
                "ported in a future release."
            ),
        }

    async def get_code_authors(path: str) -> dict[str, Any]:
        """Get author statistics for a file.

        This is a placeholder that returns a not-implemented response.
        Full functionality requires git integration.

        Args:
            path: File path relative to repo root

        Returns:
            Status indicating feature is not yet available
        """
        logger.info("git.code_authors", path=path)

        # For now, return a placeholder response
        return {
            "status": "not_implemented",
            "message": (
                "Git author analysis is not yet available in CALM. "
                "This feature requires git integration which will be "
                "ported in a future release."
            ),
            "path": path,
        }

    return {
        "index_commits": index_commits,
        "search_commits": search_commits,
        "get_file_history": get_file_history,
        "get_churn_hotspots": get_churn_hotspots,
        "get_code_authors": get_code_authors,
    }
