"""Code indexing and search tools for CALM MCP server."""

from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import structlog

from calm.embedding.base import EmbeddingService
from calm.search.collections import CollectionName
from calm.storage.base import VectorStore

from .errors import MCPError
from .validation import ValidationError, validate_query_string

logger = structlog.get_logger()

# Type alias for tool functions
ToolFunc = Callable[..., Coroutine[Any, Any, dict[str, Any]]]

# Supported languages for code search (lowercase)
SUPPORTED_LANGUAGES = [
    "python",
    "typescript",
    "javascript",
    "rust",
    "go",
    "java",
    "c",
    "cpp",
    "csharp",
    "ruby",
    "php",
    "swift",
    "kotlin",
    "scala",
]

# Project identifier constraints
PROJECT_ID_MAX_LENGTH = 100

# Default exclusion patterns
DEFAULT_EXCLUSIONS = [
    "**/.venv/**",
    "**/venv/**",
    "**/env/**",
    "**/node_modules/**",
    "**/.git/**",
    "**/.hg/**",
    "**/.svn/**",
    "**/__pycache__/**",
    "**/.tox/**",
    "**/.nox/**",
    "**/dist/**",
    "**/build/**",
    "**/target/**",
    "**/.pytest_cache/**",
    "**/.mypy_cache/**",
    "**/.ruff_cache/**",
    "**/htmlcov/**",
    "**/.eggs/**",
    "**/.worktrees/**",
    "**/*.egg-info/**",
]

# Track whether collection has been ensured
_code_collection_ensured = False


def validate_project_id(project: str) -> None:
    """Validate project identifier format.

    Args:
        project: Project identifier to validate

    Raises:
        ValidationError: If project is invalid
    """
    import re

    if not project:
        raise ValidationError("Project identifier cannot be empty")
    if len(project) > PROJECT_ID_MAX_LENGTH:
        raise ValidationError(
            f"Project identifier too long ({len(project)} chars). "
            f"Maximum: {PROJECT_ID_MAX_LENGTH} characters"
        )
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$", project):
        raise ValidationError(
            f"Invalid project identifier: '{project}'. "
            "Must contain only alphanumeric characters, dashes, and underscores, "
            "and start with an alphanumeric character"
        )


def validate_language(language: str | None) -> None:
    """Validate programming language filter.

    Args:
        language: Language to validate (or None to skip)

    Raises:
        ValidationError: If language is not supported
    """
    if language is None:
        return
    if language.lower() not in SUPPORTED_LANGUAGES:
        raise ValidationError(
            f"Unsupported language: '{language}'. "
            f"Supported languages: {', '.join(SUPPORTED_LANGUAGES)}"
        )


async def _ensure_code_collection(
    vector_store: VectorStore, code_embedder: EmbeddingService
) -> None:
    """Ensure code_units collection exists (lazy initialization)."""
    global _code_collection_ensured
    if _code_collection_ensured:
        return

    try:
        await vector_store.create_collection(
            name=CollectionName.CODE_UNITS,
            dimension=code_embedder.dimension,
            distance="cosine",
        )
        logger.info("collection_created", name=CollectionName.CODE_UNITS)
    except Exception as e:
        error_msg = str(e).lower()
        if "already exists" in error_msg or "409" in str(e):
            logger.debug("collection_exists", name=CollectionName.CODE_UNITS)
        else:
            raise

    _code_collection_ensured = True


def get_code_tools(
    vector_store: VectorStore,
    code_embedder: EmbeddingService,
    code_indexer: Any = None,
) -> dict[str, ToolFunc]:
    """Get code tool implementations for the dispatcher.

    Args:
        vector_store: Initialized vector store
        code_embedder: Initialized code embedding service

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
        """
        logger.info("code.index", directory=directory, project=project)

        # Validate parameters
        validate_project_id(project)

        # Validate directory exists
        dir_path = Path(directory).expanduser()
        if not dir_path.exists():
            raise ValidationError(f"Directory not found: {directory}")
        if not dir_path.is_dir():
            raise ValidationError(f"Not a directory: {directory}")

        if code_indexer is None:
            return {
                "status": "not_available",
                "message": "Code indexer not initialized. "
                "Restart server with real services.",
            }

        stats = await code_indexer.index_directory(
            path=str(dir_path),
            project=project,
            recursive=recursive,
            exclude_patterns=DEFAULT_EXCLUSIONS,
        )

        return {
            "status": "success",
            "project": project,
            "directory": str(dir_path),
            "files_indexed": stats.files_indexed,
            "units_indexed": stats.units_indexed,
            "files_skipped": stats.files_skipped,
            "errors": len(stats.errors),
            "duration_ms": stats.duration_ms,
        }

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
        """
        logger.info("code.search", query=query[:50], project=project)

        # Ensure collection exists
        await _ensure_code_collection(vector_store, code_embedder)

        # Validate limit
        if not 1 <= limit <= 50:
            raise ValidationError(
                f"Limit {limit} out of range. Must be between 1 and 50."
            )

        # Validate language if provided
        validate_language(language)

        # Validate optional project filter
        if project is not None:
            validate_project_id(project)

        # Validate query length
        validate_query_string(query)

        # Handle empty query
        if not query.strip():
            return {"results": [], "count": 0}

        try:
            # Generate query embedding
            query_embedding = await code_embedder.embed(query)

            # Build filters
            filters: dict[str, Any] = {}
            if project:
                filters["project"] = project
            if language:
                filters["language"] = language.lower()

            # Search
            results = await vector_store.search(
                collection=CollectionName.CODE_UNITS,
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
            error_msg = str(e).lower()
            if "not found" in error_msg or "404" in str(e):
                # Collection doesn't exist or is empty - return empty results
                logger.info("code.collection_empty")
                return {"results": [], "count": 0}
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
        """
        logger.info("code.find_similar", snippet_len=len(snippet))

        # Ensure collection exists
        await _ensure_code_collection(vector_store, code_embedder)

        # Validate snippet length
        max_length = 5000
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

        # Validate optional project filter
        if project is not None:
            validate_project_id(project)

        # Handle empty snippet
        if not snippet.strip():
            return {"results": [], "count": 0}

        try:
            # Generate embedding from snippet
            snippet_embedding = await code_embedder.embed(snippet)

            # Build filters
            filters = {"project": project} if project else None

            # Search
            results = await vector_store.search(
                collection=CollectionName.CODE_UNITS,
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
            error_msg = str(e).lower()
            if "not found" in error_msg or "404" in str(e):
                # Collection doesn't exist or is empty - return empty results
                logger.info("code.collection_empty")
                return {"results": [], "count": 0}
            logger.error("code.find_similar_failed", error=str(e), exc_info=True)
            raise MCPError(f"Failed to find similar code: {e}") from e

    return {
        "index_codebase": index_codebase,
        "search_code": search_code,
        "find_similar_code": find_similar_code,
    }
