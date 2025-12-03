# Technical Proposal: MCP Tools for Memory, Code, Git

## Problem Statement

The Learning Memory Server needs to expose its functionality to Claude Code agents via MCP tools. We need to:

1. **Define clear tool interfaces** - Input/output schemas that are intuitive for agents
2. **Wire services to tools** - Connect EmbeddingService, VectorStore, CodeIndexer, GitAnalyzer, Searcher to MCP
3. **Handle errors gracefully** - Return MCP-compliant errors with helpful messages
4. **Validate inputs** - Enforce constraints on parameters (length limits, enums, ranges)
5. **Optimize performance** - Meet latency targets for interactive use
6. **Enable testing** - Support unit tests with mocked services and integration tests with real ones

## Proposed Solution

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Server                                │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                     main.py                               │  │
│  │  - Server initialization                                  │  │
│  │  - Service dependency injection                           │  │
│  │  - Tool registration orchestration                        │  │
│  └─────────────────────┬─────────────────────────────────────┘  │
│                        │                                         │
│  ┌─────────────────────┴─────────────────────────────────────┐  │
│  │                 tools/__init__.py                          │  │
│  │  - register_all_tools(server, settings)                   │  │
│  │  - Initialize shared services                             │  │
│  │  - Delegate to module registrations                       │  │
│  └───────┬──────────────┬─────────────────┬──────────────────┘  │
│          │              │                 │                     │
│  ┌───────▼─────┐ ┌──────▼──────┐ ┌───────▼─────┐               │
│  │  memory.py  │ │   code.py   │ │   git.py    │               │
│  │             │ │             │ │             │               │
│  │ Memory      │ │ Code        │ │ Git         │               │
│  │ Tools       │ │ Tools       │ │ Tools       │               │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘               │
│         │               │               │                       │
└─────────┼───────────────┼───────────────┼───────────────────────┘
          │               │               │
          ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Service Layer                               │
│                                                                  │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐      │
│  │ EmbeddingService│ │  VectorStore  │ │ MetadataStore  │      │
│  └────────────────┘ └────────────────┘ └────────────────┘      │
│                                                                  │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐      │
│  │  CodeIndexer   │ │  GitAnalyzer   │ │   Searcher     │      │
│  └────────────────┘ └────────────────┘ └────────────────┘      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Module Structure

```
server/
├── __init__.py
├── main.py              # Server entry point
├── config.py            # ServerSettings
├── logging.py           # Log configuration
└── tools/
    ├── __init__.py      # register_all_tools()
    ├── memory.py        # Memory tools
    ├── code.py          # Code tools
    └── git.py           # Git tools
```

---

## Implementation Details

### 1. Service Initialization and Dependency Injection

**Pattern**: Services initialized once per server instance and injected into tool closures.

```python
# server/tools/__init__.py

from typing import Any
import structlog
from mcp.server import Server

from learning_memory_server.server.config import ServerSettings
from learning_memory_server.embedding import NomicEmbedding, EmbeddingService
from learning_memory_server.storage import QdrantVectorStore, VectorStore
from learning_memory_server.storage.metadata import MetadataStore
from learning_memory_server.indexers import CodeIndexer, CodeParser, TreeSitterParser
from learning_memory_server.indexers.git import GitReader, GitAnalyzer, GitPythonReader
from learning_memory_server.search import Searcher

from .memory import register_memory_tools
from .code import register_code_tools
from .git import register_git_tools

logger = structlog.get_logger()


class ServiceContainer:
    """Container for shared services used by MCP tools."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        metadata_store: MetadataStore,
        code_indexer: CodeIndexer,
        git_analyzer: GitAnalyzer,
        searcher: Searcher,
    ):
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.metadata_store = metadata_store
        self.code_indexer = code_indexer
        self.git_analyzer = git_analyzer
        self.searcher = searcher


def initialize_services(settings: ServerSettings) -> ServiceContainer:
    """Initialize all services for MCP tools.

    Args:
        settings: Server configuration

    Returns:
        ServiceContainer with initialized services
    """
    logger.info("services.initializing")

    # Core infrastructure
    embedding_service = NomicEmbedding(model_name=settings.embedding_model)
    vector_store = QdrantVectorStore(url=settings.qdrant_url)
    metadata_store = MetadataStore(db_path=settings.db_path)

    # Code indexing
    code_parser = TreeSitterParser()
    code_indexer = CodeIndexer(
        parser=code_parser,
        embedding_service=embedding_service,
        vector_store=vector_store,
        metadata_store=metadata_store,
    )

    # Git analysis (initialized lazily - only when first git tool is called)
    # Rationale: Not all users will use git tools, so avoid git repo detection overhead
    git_reader = None
    git_analyzer = None
    if settings.repo_path:
        try:
            git_reader = GitPythonReader(repo_path=settings.repo_path)
            git_analyzer = GitAnalyzer(
                git_reader=git_reader,
                embedding_service=embedding_service,
                vector_store=vector_store,
                metadata_store=metadata_store,
            )
            logger.info("git.initialized", repo_path=settings.repo_path)
        except Exception as e:
            logger.warning("git.init_failed", error=str(e))

    # Search service
    searcher = Searcher(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    logger.info("services.initialized")

    return ServiceContainer(
        embedding_service=embedding_service,
        vector_store=vector_store,
        metadata_store=metadata_store,
        code_indexer=code_indexer,
        git_analyzer=git_analyzer,
        searcher=searcher,
    )


def register_all_tools(server: Server, settings: ServerSettings) -> None:
    """Register all MCP tools with the server.

    Args:
        server: MCP Server instance
        settings: Server configuration
    """
    # Initialize shared services
    services = initialize_services(settings)

    # Register tool modules
    register_memory_tools(server, services)
    register_code_tools(server, services)
    register_git_tools(server, services)

    logger.info("tools.registered", tool_count=server.list_tools().__len__())
```

**Rationale**:
- **Single initialization**: Services created once, not per-tool-call
- **Dependency injection**: Tools receive services via closure, testable
- **Lazy git initialization**: Avoid overhead if git tools not used
- **Type safety**: ServiceContainer provides clear service access

---

### 2. Memory Tools Implementation

```python
# server/tools/memory.py

from typing import Any
from uuid import uuid4
from datetime import datetime, timezone
import structlog
from mcp.server import Server

from learning_memory_server.server.tools import ServiceContainer

logger = structlog.get_logger()

# Valid memory categories (from SPEC-001)
VALID_CATEGORIES = {"preference", "fact", "event", "workflow", "context"}


class MemoryToolError(Exception):
    """Base error for memory tool failures."""
    pass


class ValidationError(MemoryToolError):
    """Input validation failed."""
    pass


def register_memory_tools(server: Server, services: ServiceContainer) -> None:
    """Register memory tools with MCP server.

    Args:
        server: MCP Server instance
        services: Initialized service container
    """

    @server.call_tool()
    async def store_memory(
        content: str,
        category: str,
        importance: float = 0.5,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Store a new memory with semantic embedding.

        Args:
            content: Memory content (max 10,000 chars)
            category: One of: preference, fact, event, workflow, context
            importance: Importance score 0.0-1.0 (default 0.5)
            tags: Optional tags for categorization

        Returns:
            Stored memory record with ID and metadata

        Raises:
            ValidationError: If inputs are invalid
            MemoryToolError: If storage fails
        """
        logger.info("memory.store", category=category, importance=importance)

        # Validate inputs
        if category not in VALID_CATEGORIES:
            raise ValidationError(
                f"Invalid category '{category}'. "
                f"Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
            )

        # Truncate content if too long
        max_length = 10_000
        if len(content) > max_length:
            logger.warning("memory.content_truncated",
                original_len=len(content), max_len=max_length)
            content = content[:max_length]

        # Clamp importance to valid range
        if not 0.0 <= importance <= 1.0:
            logger.warning("memory.importance_clamped",
                original=importance, clamped=max(0.0, min(1.0, importance)))
            importance = max(0.0, min(1.0, importance))

        tags = tags or []

        try:
            # Generate ID and timestamp
            memory_id = str(uuid4())
            created_at = datetime.now(timezone.utc)

            # Generate embedding
            embedding = await services.embedding_service.embed(content)

            # Store in vector store
            payload = {
                "id": memory_id,
                "content": content,
                "category": category,
                "importance": importance,
                "tags": tags,
                "created_at": created_at.isoformat(),
            }

            await services.vector_store.upsert(
                collection="memories",
                id=memory_id,
                vector=embedding,
                payload=payload,
            )

            logger.info("memory.stored", memory_id=memory_id, category=category)

            return payload

        except Exception as e:
            logger.error("memory.store_failed", error=str(e), exc_info=True)
            raise MemoryToolError(f"Failed to store memory: {e}") from e


    @server.call_tool()
    async def retrieve_memories(
        query: str,
        limit: int = 10,
        category: str | None = None,
        min_importance: float = 0.0,
    ) -> dict[str, Any]:
        """Search memories semantically.

        Args:
            query: Search query
            limit: Max results (1-100, default 10)
            category: Optional category filter
            min_importance: Minimum importance filter (0.0-1.0)

        Returns:
            Search results with scores and metadata
        """
        logger.info("memory.retrieve", query=query[:50], limit=limit)

        # Validate category
        if category and category not in VALID_CATEGORIES:
            raise ValidationError(
                f"Invalid category '{category}'. "
                f"Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
            )

        # Clamp limit
        limit = max(1, min(100, limit))

        # Handle empty query
        if not query.strip():
            return {"results": [], "count": 0}

        try:
            # Generate query embedding
            query_embedding = await services.embedding_service.embed(query)

            # Build filters
            filters = {}
            if category:
                filters["category"] = category
            if min_importance > 0.0:
                filters["importance"] = {"$gte": min_importance}

            # Search
            results = await services.vector_store.search(
                collection="memories",
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

            logger.info("memory.retrieved", count=len(formatted))

            return {"results": formatted, "count": len(formatted)}

        except Exception as e:
            logger.error("memory.retrieve_failed", error=str(e), exc_info=True)
            raise MemoryToolError(f"Failed to retrieve memories: {e}") from e


    @server.call_tool()
    async def list_memories(
        category: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List memories with filters (non-semantic).

        Args:
            category: Optional category filter
            tags: Optional tag filters (ANY match)
            limit: Max results (1-200, default 50)
            offset: Pagination offset (default 0)

        Returns:
            List of memories with pagination metadata
        """
        logger.info("memory.list", category=category, limit=limit, offset=offset)

        # Validate category
        if category and category not in VALID_CATEGORIES:
            raise ValidationError(f"Invalid category '{category}'")

        # Clamp parameters
        limit = max(1, min(200, limit))
        offset = max(0, offset)

        try:
            # Build filters
            filters = {}
            if category:
                filters["category"] = category
            if tags:
                filters["tags"] = {"$in": tags}

            # Get count first
            total = await services.vector_store.count(
                collection="memories",
                filters=filters if filters else None,
            )

            # Scroll through results
            results = await services.vector_store.scroll(
                collection="memories",
                limit=limit,
                offset=offset,
                filters=filters if filters else None,
                with_vectors=False,
            )

            # Sort by created_at descending
            sorted_results = sorted(
                results,
                key=lambda x: x.payload.get("created_at", ""),
                reverse=True,
            )

            formatted = [r.payload for r in sorted_results]

            logger.info("memory.listed", count=len(formatted), total=total)

            return {
                "results": formatted,
                "count": len(formatted),
                "total": total,
            }

        except Exception as e:
            logger.error("memory.list_failed", error=str(e), exc_info=True)
            raise MemoryToolError(f"Failed to list memories: {e}") from e


    @server.call_tool()
    async def delete_memory(memory_id: str) -> dict[str, bool]:
        """Delete a memory by ID.

        Args:
            memory_id: Memory ID to delete

        Returns:
            Deletion status
        """
        logger.info("memory.delete", memory_id=memory_id)

        try:
            await services.vector_store.delete(
                collection="memories",
                id=memory_id,
            )

            logger.info("memory.deleted", memory_id=memory_id)

            return {"deleted": True}

        except Exception as e:
            logger.warning("memory.delete_failed",
                memory_id=memory_id, error=str(e))
            return {"deleted": False}
```

**Key Design Decisions**:

1. **UUID for IDs**: Random UUIDs ensure uniqueness without coordination
2. **Truncation over rejection**: Long content truncated with warning, not rejected
3. **Clamping over rejection**: Out-of-range values clamped, not rejected
4. **Soft delete failure**: delete_memory returns `deleted: false` instead of raising error
5. **Structured logging**: All operations logged with context for debugging
6. **Timezone-aware timestamps**: All datetimes are UTC with timezone info

---

### 3. Code Tools Implementation

```python
# server/tools/code.py

from typing import Any
import structlog
from mcp.server import Server

from learning_memory_server.server.tools import ServiceContainer

logger = structlog.get_logger()


class CodeToolError(Exception):
    """Base error for code tool failures."""
    pass


class ValidationError(CodeToolError):
    """Input validation failed."""
    pass


def register_code_tools(server: Server, services: ServiceContainer) -> None:
    """Register code tools with MCP server."""

    @server.call_tool()
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

        try:
            # Validate directory exists
            from pathlib import Path
            dir_path = Path(directory)
            if not dir_path.exists():
                raise ValidationError(f"Directory not found: {directory}")
            if not dir_path.is_dir():
                raise ValidationError(f"Not a directory: {directory}")

            # Index
            stats = await services.code_indexer.index_directory(
                path=directory,
                project=project,
                recursive=recursive,
            )

            logger.info("code.indexed",
                project=project,
                files=stats.files_indexed,
                units=stats.units_indexed)

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
            raise CodeToolError(f"Failed to index codebase: {e}") from e


    @server.call_tool()
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

        # Clamp limit
        limit = max(1, min(50, limit))

        # Handle empty query
        if not query.strip():
            return {"results": [], "count": 0}

        try:
            # Generate query embedding
            query_embedding = await services.embedding_service.embed(query)

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
            raise CodeToolError(f"Failed to search code: {e}") from e


    @server.call_tool()
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

        # Truncate snippet if too long
        max_length = 5_000
        if len(snippet) > max_length:
            logger.warning("code.snippet_truncated",
                original_len=len(snippet), max_len=max_length)
            snippet = snippet[:max_length]

        # Clamp limit
        limit = max(1, min(50, limit))

        # Handle empty snippet
        if not snippet.strip():
            return {"results": [], "count": 0}

        try:
            # Generate embedding from snippet
            snippet_embedding = await services.embedding_service.embed(snippet)

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
            raise CodeToolError(f"Failed to find similar code: {e}") from e
```

**Key Design Decisions**:

1. **Path validation**: Check directory exists before indexing
2. **Error accumulation**: Individual file errors collected, not thrown
3. **Snippet truncation**: Long snippets truncated for embedding performance
4. **Language normalization**: Language filter lowercased for consistency
5. **Empty query handling**: Return empty results, not an error

---

### 4. Git Tools Implementation

```python
# server/tools/git.py

from typing import Any
from datetime import datetime
import structlog
from mcp.server import Server

from learning_memory_server.server.tools import ServiceContainer

logger = structlog.get_logger()


class GitToolError(Exception):
    """Base error for git tool failures."""
    pass


class ValidationError(GitToolError):
    """Input validation failed."""
    pass


def register_git_tools(server: Server, services: ServiceContainer) -> None:
    """Register git tools with MCP server."""

    # Check if git analyzer is available
    if not services.git_analyzer:
        logger.warning("git.tools_disabled",
            reason="git_analyzer_not_initialized")
        return

    @server.call_tool()
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

        # Clamp limit
        limit = max(1, min(50, limit))

        # Parse date if provided
        since_dt = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since)
            except ValueError:
                raise ValidationError(
                    f"Invalid date format '{since}'. Use ISO format: YYYY-MM-DD"
                )

        # Handle empty query
        if not query.strip():
            return {"results": [], "count": 0}

        try:
            # Delegate to GitAnalyzer
            commits = await services.git_analyzer.search_commits(
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
            raise GitToolError(f"Failed to search commits: {e}") from e


    @server.call_tool()
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
        """
        logger.info("git.file_history", path=path, limit=limit)

        # Clamp limit
        limit = max(1, min(500, limit))

        try:
            # Delegate to GitReader
            commits = await services.git_analyzer.git_reader.get_file_history(
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
            raise GitToolError(f"Failed to get file history: {e}") from e


    @server.call_tool()
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
        """
        logger.info("git.churn_hotspots", days=days, limit=limit)

        # Clamp parameters
        days = max(1, min(365, days))
        limit = max(1, min(50, limit))

        try:
            # Delegate to GitAnalyzer
            hotspots = await services.git_analyzer.get_churn_hotspots(
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
            raise GitToolError(f"Failed to compute churn hotspots: {e}") from e


    @server.call_tool()
    async def get_code_authors(path: str) -> dict[str, Any]:
        """Get author statistics for a file.

        Args:
            path: File path relative to repo root

        Returns:
            Author contribution statistics
        """
        logger.info("git.code_authors", path=path)

        try:
            # Delegate to GitAnalyzer
            authors = await services.git_analyzer.get_file_authors(file_path=path)

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
            raise GitToolError(f"Failed to get code authors: {e}") from e
```

**Key Design Decisions**:

1. **Graceful git disable**: If git_analyzer not initialized, skip registration with warning
2. **Date parsing**: Parse ISO date strings to datetime objects with validation
3. **Parameter clamping**: Clamp days and limit to reasonable ranges
4. **FileNotFoundError handling**: Convert to ValidationError for clearer messaging
5. **Timestamp formatting**: All timestamps converted to ISO format in output

---

## Testing Strategy

### Unit Test Structure

```python
# tests/server/tools/test_memory.py

import pytest
from unittest.mock import AsyncMock, Mock
from uuid import UUID

from learning_memory_server.server.tools import ServiceContainer
from learning_memory_server.server.tools.memory import (
    register_memory_tools,
    ValidationError,
    MemoryToolError,
)


@pytest.fixture
def mock_services():
    """Create mock service container."""
    services = Mock(spec=ServiceContainer)
    services.embedding_service = AsyncMock()
    services.vector_store = AsyncMock()
    services.metadata_store = AsyncMock()
    return services


@pytest.fixture
def mock_server():
    """Create mock MCP server."""
    server = Mock()
    server.call_tool = lambda: lambda f: f  # Decorator pass-through
    return server


@pytest.mark.asyncio
async def test_store_memory_success(mock_server, mock_services):
    """Test successful memory storage."""
    # Setup
    register_memory_tools(mock_server, mock_services)
    mock_services.embedding_service.embed.return_value = [0.1] * 768
    mock_services.vector_store.upsert.return_value = None

    # Execute
    result = await store_memory(
        content="Test memory",
        category="fact",
        importance=0.8,
        tags=["test"],
    )

    # Verify
    assert UUID(result["id"])  # Valid UUID
    assert result["content"] == "Test memory"
    assert result["category"] == "fact"
    assert result["importance"] == 0.8
    assert result["tags"] == ["test"]
    assert "created_at" in result

    mock_services.embedding_service.embed.assert_called_once_with("Test memory")
    mock_services.vector_store.upsert.assert_called_once()


@pytest.mark.asyncio
async def test_store_memory_invalid_category(mock_server, mock_services):
    """Test validation error for invalid category."""
    register_memory_tools(mock_server, mock_services)

    with pytest.raises(ValidationError, match="Invalid category"):
        await store_memory(content="Test", category="invalid")


@pytest.mark.asyncio
async def test_store_memory_truncates_long_content(mock_server, mock_services):
    """Test content truncation for long inputs."""
    register_memory_tools(mock_server, mock_services)
    mock_services.embedding_service.embed.return_value = [0.1] * 768

    long_content = "x" * 15_000
    result = await store_memory(content=long_content, category="fact")

    assert len(result["content"]) == 10_000
    mock_services.embedding_service.embed.assert_called_once()


@pytest.mark.asyncio
async def test_retrieve_memories_success(mock_server, mock_services):
    """Test successful memory retrieval."""
    register_memory_tools(mock_server, mock_services)
    mock_services.embedding_service.embed.return_value = [0.1] * 768

    # Mock search results
    mock_result = Mock()
    mock_result.payload = {
        "id": "test-id",
        "content": "Test memory",
        "category": "fact",
        "importance": 0.8,
        "tags": [],
        "created_at": "2025-01-01T00:00:00Z",
    }
    mock_result.score = 0.95
    mock_services.vector_store.search.return_value = [mock_result]

    result = await retrieve_memories(query="test query", limit=10)

    assert result["count"] == 1
    assert result["results"][0]["score"] == 0.95
    assert result["results"][0]["content"] == "Test memory"


@pytest.mark.asyncio
async def test_retrieve_memories_empty_query(mock_server, mock_services):
    """Test empty query returns empty results."""
    register_memory_tools(mock_server, mock_services)

    result = await retrieve_memories(query="   ", limit=10)

    assert result["count"] == 0
    assert result["results"] == []
    mock_services.embedding_service.embed.assert_not_called()
```

### Integration Test Structure

```python
# tests/integration/test_memory_tools.py

import pytest
from learning_memory_server.embedding import MockEmbedding
from learning_memory_server.storage import InMemoryVectorStore
from learning_memory_server.storage.metadata import MetadataStore
from learning_memory_server.server.tools import ServiceContainer
from learning_memory_server.server.tools.memory import register_memory_tools


@pytest.fixture
async def real_services(tmp_path):
    """Create service container with real implementations."""
    embedding_service = MockEmbedding(dimension=768)
    vector_store = InMemoryVectorStore()
    metadata_store = MetadataStore(db_path=str(tmp_path / "test.db"))

    # Initialize collections
    await vector_store.create_collection("memories", dimension=768)

    return ServiceContainer(
        embedding_service=embedding_service,
        vector_store=vector_store,
        metadata_store=metadata_store,
        code_indexer=None,
        git_analyzer=None,
        searcher=None,
    )


@pytest.mark.asyncio
async def test_memory_workflow_end_to_end(mock_server, real_services):
    """Test full memory workflow: store, retrieve, delete."""
    register_memory_tools(mock_server, real_services)

    # Store memories
    memory1 = await store_memory("Python is dynamically typed", "fact")
    memory2 = await store_memory("JavaScript is also dynamic", "fact")

    # Retrieve
    results = await retrieve_memories("dynamic typing", limit=5)
    assert results["count"] == 2
    assert results["results"][0]["score"] > 0.5

    # Delete
    delete_result = await delete_memory(memory1["id"])
    assert delete_result["deleted"] is True

    # Verify deletion
    results = await retrieve_memories("Python", limit=5)
    assert all(r["id"] != memory1["id"] for r in results["results"])


@pytest.mark.asyncio
async def test_pagination_with_list_memories(mock_server, real_services):
    """Test pagination functionality."""
    register_memory_tools(mock_server, real_services)

    # Store 10 memories
    for i in range(10):
        await store_memory(f"Memory {i}", "fact")

    # Page 1
    page1 = await list_memories(limit=5, offset=0)
    assert page1["count"] == 5
    assert page1["total"] == 10

    # Page 2
    page2 = await list_memories(limit=5, offset=5)
    assert page2["count"] == 5
    assert page2["total"] == 10

    # Verify no overlap
    page1_ids = {r["id"] for r in page1["results"]}
    page2_ids = {r["id"] for r in page2["results"]}
    assert len(page1_ids & page2_ids) == 0
```

---

## Alternatives Considered

### 1. Global Service Singletons

**Approach**: Use global variables for services.

**Pros**:
- Simpler initialization
- No dependency injection needed

**Cons**:
- Hard to test (can't mock globals easily)
- Tight coupling
- Difficult to manage multiple instances

**Decision**: Rejected. Use ServiceContainer with dependency injection for testability.

### 2. Per-Tool Service Initialization

**Approach**: Each tool initializes its own services.

**Pros**:
- Simple per-tool code
- No shared state

**Cons**:
- Wasteful (multiple embedding service instances)
- Connection pooling defeated
- Slow startup (repeated initialization)

**Decision**: Rejected. Use shared services initialized once.

### 3. Raise Errors for All Validation Failures

**Approach**: Reject out-of-range inputs instead of clamping.

**Pros**:
- Stricter validation
- Forces caller to handle bounds

**Cons**:
- Poor UX (agent must retry with adjusted params)
- More error handling code

**Decision**: Rejected for limits/importance. Clamp with warning. Still raise for invalid enums (clearer contract).

### 4. Synchronous Tool Implementation

**Approach**: Use sync functions instead of async.

**Pros**:
- Simpler code (no await)

**Cons**:
- Inconsistent with service layer (all async)
- Blocks event loop
- Can't use async MCP features

**Decision**: Rejected. All tools async to match service layer.

---

## Implementation Plan

### Phase 1: Service Infrastructure (2 hours)
- Create ServiceContainer class
- Implement initialize_services()
- Add service registration to register_all_tools()
- Update main.py to use new registration

### Phase 2: Memory Tools (3 hours)
- Implement register_memory_tools()
- Add store_memory, retrieve_memories, list_memories, delete_memory
- Unit tests for all memory tools
- Integration test for memory workflow

### Phase 3: Code Tools (3 hours)
- Implement register_code_tools()
- Add index_codebase, search_code, find_similar_code
- Unit tests for all code tools
- Integration test for code workflow

### Phase 4: Git Tools (3 hours)
- Implement register_git_tools()
- Add search_commits, get_file_history, get_churn_hotspots, get_code_authors
- Unit tests for all git tools
- Integration test for git workflow

### Phase 5: Error Handling & Validation (2 hours)
- Consistent error response formatting
- Input validation for all tools
- Error logging and monitoring
- Edge case testing

### Phase 6: Documentation & Polish (1 hour)
- Docstrings for all tools
- Update README with tool usage examples
- Performance profiling
- Final integration test pass

**Total Estimate**: ~14 hours

---

## Success Criteria

Implementation is complete when:

1. ✅ All 13 tools registered and callable via MCP
2. ✅ Unit test coverage ≥90% for all tool modules
3. ✅ Integration tests pass with real service implementations
4. ✅ All tools have comprehensive docstrings
5. ✅ Error handling tested for all error types
6. ✅ Input validation enforced and tested
7. ✅ Type checking passes (mypy --strict)
8. ✅ Linting passes (ruff)
9. ✅ Performance targets met (measured with pytest-benchmark)
10. ✅ Manual testing: All tools work correctly via MCP client

---

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| MCP SDK breaking changes | High | Low | Pin SDK version, monitor releases |
| Service initialization failures | High | Medium | Graceful degradation, clear error messages |
| Performance regression | Medium | Medium | Benchmark tests, profiling |
| Memory leaks from service instances | Medium | Low | Resource cleanup tests, monitoring |
| Git tool failures in non-git dirs | Low | High | Graceful disable with warning |

---

## Conclusion

This proposal implements a clean, testable MCP tool layer that:

- **Separates concerns**: Tools handle validation/formatting, services handle logic
- **Enables testing**: Dependency injection makes unit tests straightforward
- **Optimizes performance**: Shared services, batch operations, result limiting
- **Handles errors gracefully**: Consistent error format, helpful messages
- **Follows existing patterns**: Async throughout, structured logging, type hints

The design prioritizes **simplicity** and **reliability** while providing a solid foundation for future tool additions (GHAP, learning, verification).
