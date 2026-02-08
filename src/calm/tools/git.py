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
    git_analyzer: Any = None,
) -> dict[str, ToolFunc]:
    """Get git tool implementations for the dispatcher.

    Args:
        vector_store: Initialized vector store
        semantic_embedder: Initialized semantic embedding service
        git_analyzer: Optional git analyzer for commit indexing and analysis

    Returns:
        Dictionary mapping tool names to their implementations
    """

    async def index_commits(
        since: str | None = None,
        limit: int | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Index git commits for semantic search.

        Args:
            since: Optional date filter (ISO format YYYY-MM-DD)
            limit: Optional max commits to index (default: all from last 5 years)
            force: Force reindex all commits (default: false, incremental)

        Returns:
            Indexing statistics
        """
        logger.info("git.index_commits", since=since, limit=limit, force=force)

        if git_analyzer is None:
            raise MCPError(
                "Git commit indexing not available. GitAnalyzer not initialized."
            )

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

        stats = await git_analyzer.index_commits(
            since=since,
            limit=limit,
            force=force,
        )

        result = {
            "status": "success",
            "commits_indexed": stats.commits_indexed,
            "commits_skipped": stats.commits_skipped,
            "duration_ms": stats.duration_ms,
            "errors": [
                {
                    "sha": err.sha,
                    "error_type": err.error_type,
                    "message": err.message,
                }
                for err in stats.errors
            ],
        }

        return result

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

        if git_analyzer is None:
            raise MCPError(
                "Git commit search not available. GitAnalyzer not initialized."
            )

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

        # Use git_analyzer to search commits
        results = await git_analyzer.search_commits(
            query=query,
            author=author,
            since=since_dt,
            limit=limit,
        )

        # Format results
        formatted = []
        for result in results:
            # Convert timestamp to ISO format if present
            timestamp = result.commit.timestamp
            if timestamp:
                timestamp = timestamp.isoformat()

            formatted.append(
                {
                    "sha": result.commit.sha,
                    "message": result.commit.message,
                    "author": result.commit.author,
                    "author_email": result.commit.author_email,
                    "timestamp": timestamp,
                    "files_changed": result.commit.files_changed,
                    "file_count": len(result.commit.files_changed),
                    "insertions": result.commit.insertions,
                    "deletions": result.commit.deletions,
                    "score": result.score,
                }
            )

        logger.info("git.commits_found", count=len(formatted))

        return {"results": formatted, "count": len(formatted)}

    async def get_file_history(
        path: str,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Get commit history for a specific file.

        Args:
            path: File path relative to repo root
            limit: Max commits (1-500, default 100)

        Returns:
            Commit history for the specified file
        """
        logger.info("git.file_history", path=path, limit=limit)

        if git_analyzer is None:
            raise MCPError(
                "Git file history not available. GitAnalyzer not initialized."
            )

        # Validate limit
        if not 1 <= limit <= 500:
            raise ValidationError(
                f"Limit {limit} out of range. Must be between 1 and 500."
            )

        try:
            commits = await git_analyzer.git_reader.get_file_history(path=path, limit=limit)
        except FileNotFoundError as e:
            raise ValidationError(f"File not found in repository: {path}") from e

        formatted = [
            {
                "sha": c.sha,
                "message": c.message,
                "author": c.author,
                "author_email": c.author_email,
                "timestamp": c.committed_at.isoformat() if c.committed_at else None,
                "files_changed": c.files_changed,
                "insertions": c.insertions,
                "deletions": c.deletions,
            }
            for c in commits
        ]

        return {"commits": formatted, "count": len(formatted), "path": path}

    async def get_churn_hotspots(
        days: int = 90,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Find files with highest change frequency.

        Args:
            days: Analysis window in days (1-365, default 90)
            limit: Max results (1-50, default 10)

        Returns:
            Files with highest change frequency
        """
        logger.info("git.churn_hotspots", days=days, limit=limit)

        if git_analyzer is None:
            raise MCPError(
                "Git churn analysis not available. GitAnalyzer not initialized."
            )

        # Validate parameters
        if not 1 <= days <= 365:
            raise ValidationError(
                f"Days {days} out of range. Must be between 1 and 365."
            )
        if not 1 <= limit <= 50:
            raise ValidationError(
                f"Limit {limit} out of range. Must be between 1 and 50."
            )

        hotspots = await git_analyzer.get_churn_hotspots(days=days, limit=limit)

        formatted = [
            {
                "path": h.path,
                "commit_count": h.commit_count,
                "total_insertions": h.total_insertions,
                "total_deletions": h.total_deletions,
                "authors": h.authors,
            }
            for h in hotspots
        ]

        return {"hotspots": formatted, "count": len(formatted)}

    async def get_code_authors(path: str) -> dict[str, Any]:
        """Get author statistics for a file.

        Args:
            path: File path relative to repo root

        Returns:
            Author statistics for the specified file
        """
        logger.info("git.code_authors", path=path)

        if git_analyzer is None:
            raise MCPError(
                "Git author analysis not available. GitAnalyzer not initialized."
            )

        try:
            authors = await git_analyzer.get_file_authors(path=path)
        except FileNotFoundError as e:
            raise ValidationError(f"File not found in repository: {path}") from e

        formatted = [
            {
                "author": a.author,
                "email": a.email,
                "line_count": a.line_count,
                "percentage": a.percentage,
                "last_commit": a.last_commit.isoformat() if a.last_commit else None,
            }
            for a in authors
        ]

        return {"authors": formatted, "count": len(formatted), "path": path}

    return {
        "index_commits": index_commits,
        "search_commits": search_commits,
        "get_file_history": get_file_history,
        "get_churn_hotspots": get_churn_hotspots,
        "get_code_authors": get_code_authors,
    }
