"""Git tools for MCP server."""

from datetime import datetime
from typing import Any

import structlog
from mcp.server import Server

from learning_memory_server.server.errors import MCPError, ValidationError
from learning_memory_server.server.tools import ServiceContainer

logger = structlog.get_logger()


def get_git_tools(services: ServiceContainer) -> dict[str, Any]:
    """Get git tool implementations for the dispatcher.

    Args:
        services: Initialized service container

    Returns:
        Dictionary mapping tool names to their implementations
    """

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

        Raises:
            ValidationError: If parameters are invalid
            MCPError: If search fails or GitAnalyzer not available
        """
        logger.info("git.search_commits", query=query[:50], author=author)

        # Check if git analyzer is available
        if not services.git_analyzer:
            raise MCPError(
                "Git commit search not available. "
                "GitAnalyzer service not initialized "
                "(SPEC-002-07 may be incomplete or no git repository detected)."
            )

        # Validate limit
        if not 1 <= limit <= 50:
            raise ValidationError(
                f"Limit {limit} out of range. Must be between 1 and 50."
            )

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
            # Delegate to GitAnalyzer
            commits = await services.git_analyzer.search_commits(  # type: ignore[attr-defined]
                query=query,
                author=author,
                since=since_dt,
                limit=limit,
            )

            # Format results
            formatted = [
                {
                    "sha": c.sha,
                    "message": c.message,
                    "author": c.author,
                    "author_email": c.author_email,
                    "timestamp": c.timestamp.isoformat(),
                    "files_changed": c.files_changed,
                    "file_count": len(c.files_changed),
                    "insertions": c.insertions,
                    "deletions": c.deletions,
                    "score": c.score,  # Added by search
                }
                for c in commits
            ]

            logger.info("git.commits_found", count=len(formatted))

            return {"results": formatted, "count": len(formatted)}

        except Exception as e:
            logger.error("git.search_commits_failed", error=str(e), exc_info=True)
            raise MCPError(f"Failed to search commits: {e}") from e

    async def get_file_history(
        path: str,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Get commit history for a specific file.

        Args:
            path: File path relative to repo root
            limit: Max commits (1-500, default 100)

        Returns:
            Commit history for the file

        Raises:
            ValidationError: If parameters are invalid or file not found
            MCPError: If operation fails or GitAnalyzer not available
        """
        logger.info("git.file_history", path=path, limit=limit)

        # Check if git analyzer is available
        if not services.git_analyzer:
            raise MCPError(
                "Git file history not available. "
                "GitAnalyzer service not initialized "
                "(SPEC-002-07 may be incomplete or no git repository detected)."
            )

        # Validate limit
        if not 1 <= limit <= 500:
            raise ValidationError(
                f"Limit {limit} out of range. Must be between 1 and 500."
            )

        try:
            # Delegate to GitReader
            commits = await services.git_analyzer.git_reader.get_file_history(  # type: ignore[attr-defined]
                file_path=path,
                limit=limit,
            )

            # Format results
            formatted = [
                {
                    "sha": c.sha,
                    "message": c.message,
                    "author": c.author,
                    "author_email": c.author_email,
                    "timestamp": c.timestamp.isoformat(),
                    "insertions": c.insertions,
                    "deletions": c.deletions,
                }
                for c in commits
            ]

            logger.info("git.file_history_retrieved", count=len(formatted))

            return {"results": formatted, "count": len(formatted)}

        except FileNotFoundError as e:
            raise ValidationError(f"File not found in repository: {path}") from e
        except Exception as e:
            logger.error("git.file_history_failed", error=str(e), exc_info=True)
            raise MCPError(f"Failed to get file history: {e}") from e

    async def get_churn_hotspots(
        days: int = 90,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Find files with highest change frequency.

        Args:
            days: Analysis window (1-365, default 90)
            limit: Max results (1-50, default 10)

        Returns:
            Files with highest churn

        Raises:
            ValidationError: If parameters are invalid
            MCPError: If operation fails or GitAnalyzer not available
        """
        logger.info("git.churn_hotspots", days=days, limit=limit)

        # Check if git analyzer is available
        if not services.git_analyzer:
            raise MCPError(
                "Git churn analysis not available. "
                "GitAnalyzer service not initialized "
                "(SPEC-002-07 may be incomplete or no git repository detected)."
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

        try:
            # Delegate to GitAnalyzer
            hotspots = await services.git_analyzer.get_churn_hotspots(  # type: ignore[attr-defined]
                days=days,
                limit=limit,
            )

            # Format results
            formatted = [
                {
                    "file_path": h.file_path,
                    "change_count": h.change_count,
                    "total_insertions": h.total_insertions,
                    "total_deletions": h.total_deletions,
                    "authors": h.authors,
                    "author_emails": h.author_emails,
                    "last_changed": h.last_changed.isoformat(),
                }
                for h in hotspots
            ]

            logger.info("git.churn_computed", count=len(formatted))

            return {"results": formatted, "count": len(formatted)}

        except Exception as e:
            logger.error("git.churn_failed", error=str(e), exc_info=True)
            raise MCPError(f"Failed to compute churn hotspots: {e}") from e

    async def get_code_authors(path: str) -> dict[str, Any]:
        """Get author statistics for a file.

        Args:
            path: File path relative to repo root

        Returns:
            Author contribution statistics

        Raises:
            ValidationError: If file not found
            MCPError: If operation fails or GitAnalyzer not available
        """
        logger.info("git.code_authors", path=path)

        # Check if git analyzer is available
        if not services.git_analyzer:
            raise MCPError(
                "Git author analysis not available. "
                "GitAnalyzer service not initialized "
                "(SPEC-002-07 may be incomplete or no git repository detected)."
            )

        try:
            # Delegate to GitAnalyzer
            authors = await services.git_analyzer.get_file_authors(file_path=path)  # type: ignore[attr-defined]

            # Format results
            formatted = [
                {
                    "author": a.author,
                    "author_email": a.author_email,
                    "commit_count": a.commit_count,
                    "lines_added": a.lines_added,
                    "lines_removed": a.lines_removed,
                    "first_commit": a.first_commit.isoformat(),
                    "last_commit": a.last_commit.isoformat(),
                }
                for a in authors
            ]

            logger.info("git.authors_retrieved", count=len(formatted))

            return {"results": formatted, "count": len(formatted)}

        except FileNotFoundError as e:
            raise ValidationError(f"File not found in repository: {path}") from e
        except Exception as e:
            logger.error("git.code_authors_failed", error=str(e), exc_info=True)
            raise MCPError(f"Failed to get code authors: {e}") from e

    return {
        "search_commits": search_commits,
        "get_file_history": get_file_history,
        "get_churn_hotspots": get_churn_hotspots,
        "get_code_authors": get_code_authors,
    }


def register_git_tools(server: Server, services: ServiceContainer) -> None:
    """Register git tools with MCP server.

    DEPRECATED: This function is kept for backwards compatibility with tests.
    The new dispatcher pattern uses get_git_tools() instead.
    """
    # No-op - tools are now registered via the central dispatcher
    pass
