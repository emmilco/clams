"""Code tools for MCP server."""

from pathlib import Path
from typing import Any

import structlog
from mcp.server import Server

from clams.config import settings
from clams.server.errors import MCPError, ValidationError
from clams.server.tools import ServiceContainer
from clams.server.tools.validation import (
    validate_language,
    validate_project_id,
)

logger = structlog.get_logger()


def get_code_tools(services: ServiceContainer) -> dict[str, Any]:
    """Get code tool implementations for the dispatcher.

    Args:
        services: Initialized service container

    Returns:
        Dictionary mapping tool names to their implementations
    """

    async def index_codebase(
        directory: str,
        project: str,
        recursive: bool = True,
    ) -> dict[str, Any]:
        """Index a directory of source code for semantic search.

        Args:
            directory: Absolute path to directory
            project: Project identifier
            recursive: Recurse subdirectories (default True)

        Returns:
            Indexing statistics

        Raises:
            ValidationError: If directory is invalid
            MCPError: If indexing fails or CodeIndexer not available
        """
        logger.info("code.index", directory=directory, project=project)

        # Check if code indexer is available
        if not services.code_indexer:
            raise MCPError(
                "Code indexing not available. "
                "CodeIndexer service not initialized (SPEC-002-06 may be incomplete)."
            )

        # Validate project identifier format
        validate_project_id(project)

        try:
            # Validate directory exists
            dir_path = Path(directory).expanduser()
            if not dir_path.exists():
                raise ValidationError(f"Directory not found: {directory}")
            if not dir_path.is_dir():
                raise ValidationError(f"Not a directory: {directory}")

            # Define default exclusion patterns to avoid indexing
            # virtual environments, dependencies, and build artifacts
            default_exclusions = [
                "**/.venv/**",
                "**/venv/**",
                "**/node_modules/**",
                "**/.git/**",
                "**/__pycache__/**",
                "**/dist/**",
                "**/build/**",
                "**/target/**",
                "**/.pytest_cache/**",
                "**/.mypy_cache/**",
                "**/.ruff_cache/**",
                "**/htmlcov/**",
                "**/.coverage",
                "**/*.egg-info/**",
            ]

            # Index
            # Note: This will need the actual CodeIndexer interface
            # when SPEC-002-06 is complete
            stats = await services.code_indexer.index_directory(  # type: ignore[attr-defined]
                path=directory,
                project=project,
                recursive=recursive,
                exclude_patterns=default_exclusions,
            )

            logger.info(
                "code.indexed",
                project=project,
                files=stats.files_indexed,
                units=stats.units_indexed,
            )

            return {
                "project": project,
                "files_indexed": stats.files_indexed,
                "units_indexed": stats.units_indexed,
                "files_skipped": stats.files_skipped,
                "errors": [
                    {
                        "file_path": e.file_path,
                        "error_type": e.error_type,
                        "message": e.message,
                    }
                    for e in stats.errors
                ],
                "duration_ms": stats.duration_ms,
            }

        except ValidationError:
            raise
        except Exception as e:
            logger.error("code.index_failed", error=str(e), exc_info=True)
            raise MCPError(f"Failed to index codebase: {e}") from e

    async def search_code(
        query: str,
        project: str | None = None,
        language: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Search indexed code semantically.

        Args:
            query: Search query
            project: Optional project filter
            language: Optional language filter (python, typescript, etc.)
            limit: Max results (1-50, default 10)

        Returns:
            Search results with scores

        Raises:
            ValidationError: If parameters are invalid
            MCPError: If search fails or CodeIndexer not available
        """
        logger.info("code.search", query=query[:50], project=project)

        # Check if code indexer is available
        if not services.code_indexer:
            raise MCPError(
                "Code search not available. "
                "CodeIndexer service not initialized (SPEC-002-06 may be incomplete)."
            )

        # Validate limit
        if not 1 <= limit <= 50:
            raise ValidationError(
                f"Limit {limit} out of range. Must be between 1 and 50."
            )

        # Validate language if provided
        validate_language(language)

        # Handle empty query
        if not query.strip():
            return {"results": [], "count": 0}

        try:
            # Generate query embedding
            query_embedding = await services.code_embedder.embed(query)

            # Build filters
            filters = {}
            if project:
                filters["project"] = project
            if language:
                filters["language"] = language.lower()

            # Search
            results = await services.vector_store.search(
                collection="code_units",
                query=query_embedding,
                limit=limit,
                filters=filters if filters else None,
            )

            # Format results
            formatted = [
                {
                    **result.payload,
                    "score": result.score,
                }
                for result in results
            ]

            logger.info("code.searched", count=len(formatted))

            return {"results": formatted, "count": len(formatted)}

        except Exception as e:
            logger.error("code.search_failed", error=str(e), exc_info=True)
            raise MCPError(f"Failed to search code: {e}") from e

    async def find_similar_code(
        snippet: str,
        project: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Find code similar to a given snippet.

        Args:
            snippet: Code snippet (max 5,000 chars)
            project: Optional project filter
            limit: Max results (1-50, default 10)

        Returns:
            Similar code units with scores

        Raises:
            ValidationError: If parameters are invalid
            MCPError: If search fails or CodeIndexer not available
        """
        logger.info("code.find_similar", snippet_len=len(snippet))

        # Check if code indexer is available
        if not services.code_indexer:
            raise MCPError(
                "Code similarity search not available. "
                "CodeIndexer service not initialized (SPEC-002-06 may be incomplete)."
            )

        # Validate snippet length (no silent truncation per spec)
        max_length = settings.tools.snippet_max_length
        if len(snippet) > max_length:
            raise ValidationError(
                f"Snippet too long ({len(snippet)} chars). "
                f"Maximum allowed is {max_length} characters."
            )

        # Validate limit
        if not 1 <= limit <= 50:
            raise ValidationError(
                f"Limit {limit} out of range. Must be between 1 and 50."
            )

        # Handle empty snippet
        if not snippet.strip():
            return {"results": [], "count": 0}

        try:
            # Generate embedding from snippet
            snippet_embedding = await services.code_embedder.embed(snippet)

            # Build filters
            filters = {"project": project} if project else None

            # Search
            results = await services.vector_store.search(
                collection="code_units",
                query=snippet_embedding,
                limit=limit,
                filters=filters,
            )

            # Format results
            formatted = [
                {
                    **result.payload,
                    "score": result.score,
                }
                for result in results
            ]

            logger.info("code.similar_found", count=len(formatted))

            return {"results": formatted, "count": len(formatted)}

        except Exception as e:
            logger.error("code.find_similar_failed", error=str(e), exc_info=True)
            raise MCPError(f"Failed to find similar code: {e}") from e

    return {
        "index_codebase": index_codebase,
        "search_code": search_code,
        "find_similar_code": find_similar_code,
    }


def register_code_tools(server: Server, services: ServiceContainer) -> None:
    """Register code tools with MCP server.

    DEPRECATED: This function is kept for backwards compatibility with tests.
    The new dispatcher pattern uses get_code_tools() instead.
    """
    # No-op - tools are now registered via the central dispatcher
    pass
