"""MCP tool implementations and service container."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
from mcp.server import Server
from mcp.types import Tool

from learning_memory_server.clustering import Clusterer, ExperienceClusterer
from learning_memory_server.embedding import EmbeddingService
from learning_memory_server.observation import (
    ObservationCollector,
    ObservationPersister,
)
from learning_memory_server.search import Searcher
from learning_memory_server.server.config import ServerSettings
from learning_memory_server.storage import VectorStore
from learning_memory_server.storage.metadata import MetadataStore
from learning_memory_server.storage.qdrant import QdrantVectorStore
from learning_memory_server.values import ValueStore

logger = structlog.get_logger()


@dataclass
class ServiceContainer:
    """Container for shared services used by MCP tools.

    Services that depend on incomplete specs (SPEC-002-06, 07, 09) are optional
    and initialized lazily when needed.

    IMPORTANT: Call close() when done to release resources and prevent
    process hangs during shutdown (the MetadataStore's aiosqlite connection
    creates a non-daemon thread that blocks interpreter exit).
    """

    embedding_service: EmbeddingService
    vector_store: VectorStore
    metadata_store: MetadataStore
    code_indexer: object | None = None  # Will be CodeIndexer when SPEC-002-06 complete
    git_analyzer: object | None = None  # Will be GitAnalyzer when SPEC-002-07 complete
    searcher: object | None = None  # Will be Searcher when SPEC-002-09 complete

    async def close(self) -> None:
        """Close all services and release resources.

        This must be called to prevent process hangs during shutdown.
        The MetadataStore's aiosqlite connection creates a non-daemon
        background thread that blocks Python interpreter exit if not closed.
        """
        if self.metadata_store:
            await self.metadata_store.close()
            logger.debug("services.metadata_store_closed")


async def initialize_services(
    settings: ServerSettings,
    embedding_service: EmbeddingService,
) -> ServiceContainer:
    """Initialize all services for MCP tools.

    Core services (embedding, vector, metadata) are always initialized.
    Optional services (code, git, search) are only initialized if their
    dependencies (SPEC-002-06, 07, 09) are complete.

    Args:
        settings: Server configuration
        embedding_service: Pre-initialized embedding service

    Returns:
        ServiceContainer with initialized services
    """
    logger.info("services.initializing")

    # Core infrastructure (always available)
    # Use provided embedding service (no more NomicEmbedding() call here)
    vector_store = QdrantVectorStore(url=settings.qdrant_url)
    metadata_store = MetadataStore(db_path=settings.sqlite_path)
    await metadata_store.initialize()

    # Code indexing (optional - graceful degradation)
    code_indexer = None
    try:
        from learning_memory_server.indexers import (
            CodeIndexer,
            TreeSitterParser,
        )
        code_parser = TreeSitterParser()
        code_indexer = CodeIndexer(
            parser=code_parser,
            embedding_service=embedding_service,
            vector_store=vector_store,
            metadata_store=metadata_store,
        )
        logger.info("code.initialized")
    except ImportError as e:
        logger.warning("code.init_skipped", reason="module_not_found", error=str(e))
    except Exception as e:
        logger.warning("code.init_failed", error=str(e))

    # Git analysis (optional - graceful degradation)
    git_analyzer = None

    # Auto-detect repo if not configured
    repo_path_to_use = settings.repo_path
    if not repo_path_to_use:
        try:
            from git import Repo
            repo = Repo(search_parent_directories=True)
            repo_path_to_use = str(repo.working_dir) if repo.working_dir else None
            logger.info("git.repo_auto_detected", repo_path=repo_path_to_use)
        except Exception:
            # Not in a git repo or git not available - that's fine
            logger.debug("git.auto_detect_failed", reason="no_repo_found")

    if repo_path_to_use:
        try:
            from learning_memory_server.git import (
                GitAnalyzer,
                GitPythonReader,
            )
            git_reader = GitPythonReader(repo_path=repo_path_to_use)
            git_analyzer = GitAnalyzer(
                git_reader=git_reader,
                embedding_service=embedding_service,
                vector_store=vector_store,
                metadata_store=metadata_store,
            )
            logger.info("git.initialized", repo_path=repo_path_to_use)
        except ImportError as e:
            logger.warning("git.init_skipped", reason="module_not_found", error=str(e))
        except Exception as e:
            logger.warning(
                "git.init_failed", repo_path=repo_path_to_use, error=str(e)
            )
    else:
        logger.info("git.init_skipped", reason="no_repo_path")

    # Note: Searcher is initialized separately in register_all_tools()
    # since it's used by search tools, not by code/git tools
    searcher = None

    logger.info(
        "services.initialized",
        has_code=code_indexer is not None,
        has_git=git_analyzer is not None,
        has_searcher=searcher is not None,
    )

    return ServiceContainer(
        embedding_service=embedding_service,
        vector_store=vector_store,
        metadata_store=metadata_store,
        code_indexer=code_indexer,
        git_analyzer=git_analyzer,
        searcher=searcher,
    )


def _get_all_tool_definitions() -> list[Tool]:
    """Get all tool definitions with their JSON schemas.

    This function defines the tool metadata that is returned by the
    list_tools handler. Each tool must have a name, description, and
    inputSchema that matches the actual tool implementation.

    Returns:
        List of Tool definitions
    """
    return [
        # === Memory Tools (SPEC-002-11) ===
        Tool(
            name="store_memory",
            description="Store a new memory with semantic embedding.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Memory content (max 10,000 chars)",
                    },
                    "category": {
                        "type": "string",
                        "description": "Category: preference, fact, event, workflow, context, error, decision",
                        "enum": ["preference", "fact", "event", "workflow", "context", "error", "decision"],
                    },
                    "importance": {
                        "type": "number",
                        "description": "Importance score 0.0-1.0 (default 0.5)",
                        "default": 0.5,
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for categorization",
                    },
                },
                "required": ["content", "category"],
            },
        ),
        Tool(
            name="retrieve_memories",
            description="Search memories semantically.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (1-100, default 10)",
                        "default": 10,
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category filter",
                        "enum": ["preference", "fact", "event", "workflow", "context", "error", "decision"],
                    },
                    "min_importance": {
                        "type": "number",
                        "description": "Minimum importance filter (0.0-1.0)",
                        "default": 0.0,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="list_memories",
            description="List memories with filters (non-semantic).",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Optional category filter",
                        "enum": ["preference", "fact", "event", "workflow", "context", "error", "decision"],
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tag filters (ANY match)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (1-200, default 50)",
                        "default": 50,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset (default 0)",
                        "default": 0,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="delete_memory",
            description="Delete a memory by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "Memory ID to delete",
                    },
                },
                "required": ["memory_id"],
            },
        ),
        # === Code Tools (SPEC-002-11) ===
        Tool(
            name="index_codebase",
            description="Index a directory of source code for semantic search.",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Absolute path to directory",
                    },
                    "project": {
                        "type": "string",
                        "description": "Project identifier",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Recurse subdirectories (default True)",
                        "default": True,
                    },
                },
                "required": ["directory", "project"],
            },
        ),
        Tool(
            name="search_code",
            description="Search indexed code semantically.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "project": {
                        "type": "string",
                        "description": "Optional project filter",
                    },
                    "language": {
                        "type": "string",
                        "description": "Optional language filter (python, typescript, etc.)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (1-50, default 10)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="find_similar_code",
            description="Find code similar to a given snippet.",
            inputSchema={
                "type": "object",
                "properties": {
                    "snippet": {
                        "type": "string",
                        "description": "Code snippet (max 5,000 chars)",
                    },
                    "project": {
                        "type": "string",
                        "description": "Optional project filter",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (1-50, default 10)",
                        "default": 10,
                    },
                },
                "required": ["snippet"],
            },
        ),
        # === Git Tools (SPEC-002-11) ===
        Tool(
            name="index_commits",
            description="Index git commits for semantic search.",
            inputSchema={
                "type": "object",
                "properties": {
                    "since": {
                        "type": "string",
                        "description": "Optional date filter (ISO format YYYY-MM-DD)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Optional max commits to index (default: all from last 5 years)",
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Force reindex all commits (default: false, incremental)",
                        "default": False,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="search_commits",
            description="Search git commits semantically.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "author": {
                        "type": "string",
                        "description": "Optional author name filter",
                    },
                    "since": {
                        "type": "string",
                        "description": "Optional date filter (ISO format YYYY-MM-DD)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (1-50, default 10)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_file_history",
            description="Get commit history for a specific file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to repo root",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max commits (1-500, default 100)",
                        "default": 100,
                    },
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="get_churn_hotspots",
            description="Find files with highest change frequency.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Analysis window in days (1-365, default 90)",
                        "default": 90,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (1-50, default 10)",
                        "default": 10,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_code_authors",
            description="Get author statistics for a file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to repo root",
                    },
                },
                "required": ["path"],
            },
        ),
        # === GHAP Tools (SPEC-002-15) ===
        Tool(
            name="start_ghap",
            description="Begin tracking a new GHAP (Goal-Hypothesis-Action-Prediction) entry.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Task domain",
                        "enum": ["debugging", "refactoring", "feature", "optimization", "testing", "documentation", "other"],
                    },
                    "strategy": {
                        "type": "string",
                        "description": "Problem-solving strategy",
                        "enum": ["systematic-elimination", "trial-and-error", "research-first", "divide-and-conquer", "root-cause-analysis", "copy-from-similar", "check-assumptions", "read-the-error", "ask-user"],
                    },
                    "goal": {
                        "type": "string",
                        "description": "What meaningful change are you trying to make?",
                    },
                    "hypothesis": {
                        "type": "string",
                        "description": "What do you believe about the situation?",
                    },
                    "action": {
                        "type": "string",
                        "description": "What are you doing based on this belief?",
                    },
                    "prediction": {
                        "type": "string",
                        "description": "If your hypothesis is correct, what will you observe?",
                    },
                },
                "required": ["domain", "strategy", "goal", "hypothesis", "action", "prediction"],
            },
        ),
        Tool(
            name="update_ghap",
            description="Update the current GHAP entry.",
            inputSchema={
                "type": "object",
                "properties": {
                    "hypothesis": {
                        "type": "string",
                        "description": "Updated hypothesis",
                    },
                    "action": {
                        "type": "string",
                        "description": "Updated action",
                    },
                    "prediction": {
                        "type": "string",
                        "description": "Updated prediction",
                    },
                    "strategy": {
                        "type": "string",
                        "description": "Updated strategy",
                        "enum": ["systematic-elimination", "trial-and-error", "research-first", "divide-and-conquer", "root-cause-analysis", "copy-from-similar", "check-assumptions", "read-the-error", "ask-user"],
                    },
                    "note": {
                        "type": "string",
                        "description": "Additional note (for history tracking)",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="resolve_ghap",
            description="Mark the current GHAP entry as resolved.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Resolution status",
                        "enum": ["confirmed", "falsified", "abandoned"],
                    },
                    "result": {
                        "type": "string",
                        "description": "What actually happened",
                    },
                    "surprise": {
                        "type": "string",
                        "description": "What was unexpected (required for falsified)",
                    },
                    "root_cause": {
                        "type": "object",
                        "description": "Why hypothesis was wrong (required for falsified)",
                        "properties": {
                            "category": {
                                "type": "string",
                                "enum": ["incomplete_information", "wrong_assumption", "unexpected_behavior", "environment_issue", "other"],
                            },
                            "description": {"type": "string"},
                        },
                    },
                    "lesson": {
                        "type": "object",
                        "description": "What worked (recommended for confirmed/falsified)",
                        "properties": {
                            "what_worked": {"type": "string"},
                            "takeaway": {"type": "string"},
                        },
                    },
                },
                "required": ["status", "result"],
            },
        ),
        Tool(
            name="get_active_ghap",
            description="Get the current active GHAP entry.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="list_ghap_entries",
            description="List recent GHAP entries with filters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default 20, max 100)",
                        "default": 20,
                    },
                    "domain": {
                        "type": "string",
                        "description": "Filter by domain",
                        "enum": ["debugging", "refactoring", "feature", "optimization", "testing", "documentation", "other"],
                    },
                    "outcome": {
                        "type": "string",
                        "description": "Filter by outcome status",
                        "enum": ["confirmed", "falsified", "abandoned"],
                    },
                    "since": {
                        "type": "string",
                        "description": "Filter by creation date (ISO 8601 format)",
                    },
                },
                "required": [],
            },
        ),
        # === Learning Tools (SPEC-002-15) ===
        Tool(
            name="get_clusters",
            description="Get cluster information for a given axis.",
            inputSchema={
                "type": "object",
                "properties": {
                    "axis": {
                        "type": "string",
                        "description": "Axis to cluster",
                        "enum": ["full", "strategy", "surprise", "root_cause"],
                    },
                },
                "required": ["axis"],
            },
        ),
        Tool(
            name="get_cluster_members",
            description="Get experiences in a specific cluster.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cluster_id": {
                        "type": "string",
                        "description": "Cluster ID (format: 'axis_label', e.g., 'full_0')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default 50, max 100)",
                        "default": 50,
                    },
                },
                "required": ["cluster_id"],
            },
        ),
        Tool(
            name="validate_value",
            description="Validate a proposed value statement against a cluster centroid.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Proposed value statement (max 500 chars)",
                    },
                    "cluster_id": {
                        "type": "string",
                        "description": "Target cluster ID",
                    },
                },
                "required": ["text", "cluster_id"],
            },
        ),
        Tool(
            name="store_value",
            description="Store a validated value statement.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Value statement (max 500 chars)",
                    },
                    "cluster_id": {
                        "type": "string",
                        "description": "Associated cluster ID",
                    },
                    "axis": {
                        "type": "string",
                        "description": "Axis (full, strategy, surprise, root_cause)",
                        "enum": ["full", "strategy", "surprise", "root_cause"],
                    },
                },
                "required": ["text", "cluster_id", "axis"],
            },
        ),
        Tool(
            name="list_values",
            description="List stored values with optional axis filter.",
            inputSchema={
                "type": "object",
                "properties": {
                    "axis": {
                        "type": "string",
                        "description": "Filter by axis (optional)",
                        "enum": ["full", "strategy", "surprise", "root_cause"],
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default 20, max 100)",
                        "default": 20,
                    },
                },
                "required": [],
            },
        ),
        # === Search Tools (SPEC-002-15) ===
        Tool(
            name="search_experiences",
            description="Search experiences semantically across axes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "axis": {
                        "type": "string",
                        "description": "Axis to search (default: full)",
                        "enum": ["full", "strategy", "surprise", "root_cause"],
                        "default": "full",
                    },
                    "domain": {
                        "type": "string",
                        "description": "Filter by domain (optional)",
                        "enum": ["debugging", "refactoring", "feature", "optimization", "testing", "documentation", "other"],
                    },
                    "outcome": {
                        "type": "string",
                        "description": "Filter by outcome status (optional)",
                        "enum": ["confirmed", "falsified", "abandoned"],
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default 10, max 50)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
        # === Health Check ===
        Tool(
            name="ping",
            description="Health check endpoint.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


async def register_all_tools(
    server: Server,
    settings: ServerSettings,
    embedding_service: EmbeddingService,
) -> ServiceContainer:
    """Register all MCP tools with the server.

    Args:
        server: MCP Server instance
        settings: Server configuration
        embedding_service: Pre-initialized embedding service

    Returns:
        ServiceContainer with initialized services (caller should call close()
        when done to release resources and prevent shutdown hangs)
    """
    # Initialize shared services
    services = await initialize_services(settings, embedding_service)

    # Import and register tool modules
    from .code import register_code_tools
    from .ghap import register_ghap_tools
    from .git import register_git_tools
    from .learning import register_learning_tools
    from .memory import register_memory_tools
    from .search import register_search_tools

    # Register memory, code, and git tools (from SPEC-002-11)
    register_memory_tools(server, services)
    register_code_tools(server, services)
    register_git_tools(server, services)

    # Initialize and register GHAP tools (from SPEC-002-15)
    observation_collector = ObservationCollector(
        journal_dir=Path(settings.journal_path).expanduser(),
    )
    observation_persister = ObservationPersister(
        embedding_service=services.embedding_service,
        vector_store=services.vector_store,
    )
    register_ghap_tools(server, observation_collector, observation_persister)

    # Initialize and register learning tools (from SPEC-002-15)
    clusterer = Clusterer(
        min_cluster_size=5,
        min_samples=3,
        metric="cosine",
        cluster_selection_method="eom",
    )
    experience_clusterer = ExperienceClusterer(
        vector_store=services.vector_store,
        clusterer=clusterer,
    )
    value_store = ValueStore(
        embedding_service=services.embedding_service,
        vector_store=services.vector_store,
        clusterer=experience_clusterer,
    )
    register_learning_tools(server, experience_clusterer, value_store)

    # Initialize and register search tools (from SPEC-002-15)
    searcher = Searcher(
        embedding_service=services.embedding_service,
        vector_store=services.vector_store,
    )
    register_search_tools(server, searcher)

    # Build tool registry for dispatching
    tool_registry: dict[str, Any] = {}

    # Import tool implementations (they register themselves in the registry)
    from .code import get_code_tools
    from .ghap import get_ghap_tools
    from .git import get_git_tools
    from .learning import get_learning_tools
    from .memory import get_memory_tools
    from .search import get_search_tools

    # Register all tool implementations
    tool_registry.update(get_memory_tools(services))
    tool_registry.update(get_code_tools(services))
    tool_registry.update(get_git_tools(services))
    tool_registry.update(get_ghap_tools(observation_collector, observation_persister))
    tool_registry.update(get_learning_tools(experience_clusterer, value_store))
    tool_registry.update(get_search_tools(searcher))

    # Add ping tool
    async def ping_impl() -> str:
        return "pong"

    tool_registry["ping"] = ping_impl

    # Register the tool dispatcher - handles ALL tool calls
    @server.call_tool()  # type: ignore[untyped-decorator]
    async def handle_call_tool(
        name: str, arguments: dict[str, Any]
    ) -> list[Any]:
        """Dispatch tool calls to the appropriate implementation.

        Args:
            name: Tool name
            arguments: Tool arguments dict

        Returns:
            Tool result as a list of content items
        """
        import json

        from mcp.types import TextContent

        if name not in tool_registry:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        tool_func = tool_registry[name]

        try:
            # Call the tool with unpacked arguments
            result = await tool_func(**arguments)

            # Convert result to TextContent
            if isinstance(result, str):
                return [TextContent(type="text", text=result)]
            elif isinstance(result, dict):
                return [TextContent(type="text", text=json.dumps(result, default=str))]
            elif isinstance(result, list):
                return [TextContent(type="text", text=json.dumps(result, default=str))]
            else:
                return [TextContent(type="text", text=str(result))]

        except Exception as e:
            logger.error("tool.call_failed", tool=name, error=str(e), exc_info=True)
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    # Register list_tools handler - REQUIRED for Claude Code to discover tools
    @server.list_tools()  # type: ignore[no-untyped-call, untyped-decorator]
    async def handle_list_tools() -> list[Tool]:
        """Return all available tools with their schemas.

        This handler is required by the MCP protocol. Without it,
        clients cannot discover what tools are available.
        """
        return _get_all_tool_definitions()

    logger.info(
        "tools.registered",
        has_code=services.code_indexer is not None,
        has_git=services.git_analyzer is not None,
        has_searcher=services.searcher is not None,
        tool_count=len(_get_all_tool_definitions()),
    )

    return services
