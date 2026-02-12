"""CALM MCP Server application.

This module provides the MCP server for CALM with full tool registration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from mcp.server import Server
from mcp.types import TextContent, Tool

from calm.config import settings

if TYPE_CHECKING:
    from calm.embedding.base import EmbeddingService
    from calm.storage.base import VectorStore

logger = structlog.get_logger()

# Domain and strategy enums for tool schemas
DOMAINS = [
    "debugging",
    "refactoring",
    "feature",
    "testing",
    "configuration",
    "documentation",
    "performance",
    "security",
    "integration",
]

STRATEGIES = [
    "systematic-elimination",
    "trial-and-error",
    "research-first",
    "divide-and-conquer",
    "root-cause-analysis",
    "copy-from-similar",
    "check-assumptions",
    "read-the-error",
    "ask-user",
]

ROOT_CAUSE_CATEGORIES = [
    "wrong-assumption",
    "missing-knowledge",
    "oversight",
    "environment-issue",
    "misleading-symptom",
    "incomplete-fix",
    "wrong-scope",
    "test-isolation",
    "timing-issue",
]

VALID_AXES = ["full", "strategy", "surprise", "root_cause"]

OUTCOME_STATUS_VALUES = ["confirmed", "falsified", "abandoned"]


def _get_all_tool_definitions() -> list[Tool]:
    """Get all tool definitions with their JSON schemas."""
    return [
        # === Memory Tools ===
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
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Max results (1-100, default 10)", "default": 10},
                    "category": {
                        "type": "string",
                        "description": "Optional category filter",
                        "enum": ["preference", "fact", "event", "workflow", "context", "error", "decision"],
                    },
                    "min_importance": {"type": "number", "description": "Minimum importance filter (0.0-1.0)", "default": 0},
                    "search_mode": {
                        "type": "string",
                        "description": "Search mode: semantic (vector similarity), keyword (text matching), or hybrid (both)",
                        "enum": ["semantic", "keyword", "hybrid"],
                        "default": "semantic",
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
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tag filters (ANY match)"},
                    "limit": {"type": "integer", "description": "Max results (1-200, default 50)", "default": 50},
                    "offset": {"type": "integer", "description": "Pagination offset (default 0)", "default": 0},
                },
                "required": [],
            },
        ),
        Tool(
            name="delete_memory",
            description="Delete a memory by ID.",
            inputSchema={
                "type": "object",
                "properties": {"memory_id": {"type": "string", "description": "Memory ID to delete"}},
                "required": ["memory_id"],
            },
        ),
        # === Code Tools ===
        Tool(
            name="index_codebase",
            description="Index a directory of source code for semantic search.",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Absolute path to directory"},
                    "project": {"type": "string", "description": "Project identifier"},
                    "recursive": {"type": "boolean", "description": "Recurse subdirectories (default True)", "default": True},
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
                    "query": {"type": "string", "description": "Search query"},
                    "project": {"type": "string", "description": "Optional project filter"},
                    "language": {"type": "string", "description": "Optional language filter (python, typescript, etc.)"},
                    "limit": {"type": "integer", "description": "Max results (1-50, default 10)", "default": 10},
                    "search_mode": {
                        "type": "string",
                        "description": "Search mode: semantic (vector similarity), keyword (text matching), or hybrid (both)",
                        "enum": ["semantic", "keyword", "hybrid"],
                        "default": "semantic",
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
                    "snippet": {"type": "string", "description": "Code snippet (max 5,000 chars)"},
                    "project": {"type": "string", "description": "Optional project filter"},
                    "limit": {"type": "integer", "description": "Max results (1-50, default 10)", "default": 10},
                },
                "required": ["snippet"],
            },
        ),
        # === Git Tools ===
        Tool(
            name="index_commits",
            description="Index git commits for semantic search.",
            inputSchema={
                "type": "object",
                "properties": {
                    "since": {"type": "string", "description": "Optional date filter (ISO format YYYY-MM-DD)"},
                    "limit": {"type": "integer", "description": "Optional max commits to index (default: all from last 5 years)"},
                    "force": {"type": "boolean", "description": "Force reindex all commits (default: false, incremental)", "default": False},
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
                    "query": {"type": "string", "description": "Search query"},
                    "author": {"type": "string", "description": "Optional author name filter"},
                    "since": {"type": "string", "description": "Optional date filter (ISO format YYYY-MM-DD)"},
                    "limit": {"type": "integer", "description": "Max results (1-50, default 10)", "default": 10},
                    "search_mode": {
                        "type": "string",
                        "description": "Search mode: semantic (vector similarity), keyword (text matching), or hybrid (both)",
                        "enum": ["semantic", "keyword", "hybrid"],
                        "default": "semantic",
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
                    "path": {"type": "string", "description": "File path relative to repo root"},
                    "limit": {"type": "integer", "description": "Max commits (1-500, default 100)", "default": 100},
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
                    "days": {"type": "integer", "description": "Analysis window in days (1-365, default 90)", "default": 90},
                    "limit": {"type": "integer", "description": "Max results (1-50, default 10)", "default": 10},
                },
                "required": [],
            },
        ),
        Tool(
            name="get_code_authors",
            description="Get author statistics for a file.",
            inputSchema={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File path relative to repo root"}},
                "required": ["path"],
            },
        ),
        # === GHAP Tools ===
        Tool(
            name="start_ghap",
            description="Begin tracking a new GHAP (Goal-Hypothesis-Action-Prediction) entry.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Task domain", "enum": DOMAINS},
                    "strategy": {"type": "string", "description": "Problem-solving strategy", "enum": STRATEGIES},
                    "goal": {"type": "string", "description": "What meaningful change are you trying to make?"},
                    "hypothesis": {"type": "string", "description": "What do you believe about the situation?"},
                    "action": {"type": "string", "description": "What are you doing based on this belief?"},
                    "prediction": {"type": "string", "description": "If your hypothesis is correct, what will you observe?"},
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
                    "hypothesis": {"type": "string", "description": "Updated hypothesis"},
                    "action": {"type": "string", "description": "Updated action"},
                    "prediction": {"type": "string", "description": "Updated prediction"},
                    "strategy": {"type": "string", "description": "Updated strategy", "enum": STRATEGIES},
                    "note": {"type": "string", "description": "Additional note (for history tracking)"},
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
                    "status": {"type": "string", "description": "Resolution status", "enum": OUTCOME_STATUS_VALUES},
                    "result": {"type": "string", "description": "What actually happened"},
                    "surprise": {"type": "string", "description": "What was unexpected (required for falsified)"},
                    "root_cause": {
                        "type": "object",
                        "description": "Why hypothesis was wrong (required for falsified)",
                        "properties": {
                            "category": {"type": "string", "enum": ROOT_CAUSE_CATEGORIES},
                            "description": {"type": "string"},
                        },
                    },
                    "lesson": {
                        "type": "object",
                        "description": "What worked (recommended for confirmed/falsified)",
                        "properties": {"what_worked": {"type": "string"}, "takeaway": {"type": "string"}},
                    },
                },
                "required": ["status", "result"],
            },
        ),
        Tool(
            name="get_active_ghap",
            description="Get the current active GHAP entry.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="list_ghap_entries",
            description="List recent GHAP entries with filters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Maximum results (default 20, max 100)", "default": 20},
                    "domain": {"type": "string", "description": "Filter by domain", "enum": DOMAINS},
                    "outcome": {"type": "string", "description": "Filter by outcome status", "enum": OUTCOME_STATUS_VALUES},
                    "since": {"type": "string", "description": "Filter by creation date (ISO 8601 format)"},
                },
                "required": [],
            },
        ),
        # === Learning Tools ===
        Tool(
            name="search_experiences",
            description="Search experiences semantically across axes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "axis": {"type": "string", "description": "Axis to search (default: full)", "enum": VALID_AXES, "default": "full"},
                    "domain": {"type": "string", "description": "Filter by domain (optional)", "enum": DOMAINS},
                    "outcome": {"type": "string", "description": "Filter by outcome status (optional)", "enum": OUTCOME_STATUS_VALUES},
                    "limit": {"type": "integer", "description": "Maximum results (default 10, max 50)", "default": 10},
                    "search_mode": {
                        "type": "string",
                        "description": "Search mode: semantic (vector similarity), keyword (text matching), or hybrid (both)",
                        "enum": ["semantic", "keyword", "hybrid"],
                        "default": "semantic",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_clusters",
            description="Get cluster information for a given axis.",
            inputSchema={
                "type": "object",
                "properties": {"axis": {"type": "string", "description": "Axis to cluster", "enum": VALID_AXES}},
                "required": ["axis"],
            },
        ),
        Tool(
            name="get_cluster_members",
            description="Get experiences in a specific cluster.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cluster_id": {"type": "string", "description": "Cluster ID (format: 'axis_label', e.g., 'full_0')"},
                    "limit": {"type": "integer", "description": "Maximum results (default 50, max 100)", "default": 50},
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
                    "text": {"type": "string", "description": "Proposed value statement (max 500 chars)"},
                    "cluster_id": {"type": "string", "description": "Target cluster ID"},
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
                    "text": {"type": "string", "description": "Value statement (max 500 chars)"},
                    "cluster_id": {"type": "string", "description": "Associated cluster ID"},
                    "axis": {"type": "string", "description": "Axis (full, strategy, surprise, root_cause)", "enum": VALID_AXES},
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
                    "axis": {"type": "string", "description": "Filter by axis (optional)", "enum": VALID_AXES},
                    "limit": {"type": "integer", "description": "Maximum results (default 20, max 100)", "default": 20},
                },
                "required": [],
            },
        ),
        # === Context Tools ===
        Tool(
            name="assemble_context",
            description="Assemble relevant context for a user prompt.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "User's prompt text"},
                    "context_types": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["values", "experiences"]},
                        "description": "Types to include (default: both)",
                    },
                    "limit": {"type": "integer", "description": "Maximum items per type (default 10)", "default": 10},
                    "max_tokens": {"type": "integer", "description": "Approximate token budget (default 1500)", "default": 1500},
                },
                "required": ["query"],
            },
        ),
        # === Session Journal Tools ===
        Tool(
            name="store_journal_entry",
            description="Store a new session journal entry with optional log capture.",
            inputSchema={
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Session summary text (required)",
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "The working directory of the session (required)",
                    },
                    "friction_points": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of friction points encountered",
                    },
                    "next_steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Recommended next steps",
                    },
                    "session_log_content": {
                        "type": "string",
                        "description": "Raw session log content to store",
                    },
                },
                "required": ["summary", "working_directory"],
            },
        ),
        Tool(
            name="list_journal_entries",
            description="List session journal entries with optional filters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "unreflected_only": {
                        "type": "boolean",
                        "description": "Only return entries where reflected_at is NULL",
                        "default": False,
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Filter by project name",
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Filter by exact working directory",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum entries to return (default 50)",
                        "default": 50,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_journal_entry",
            description="Get full details of a journal entry.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_id": {
                        "type": "string",
                        "description": "The entry ID",
                    },
                    "include_log": {
                        "type": "boolean",
                        "description": "Include the full session log content",
                        "default": False,
                    },
                },
                "required": ["entry_id"],
            },
        ),
        Tool(
            name="mark_entries_reflected",
            description="Mark entries as reflected and optionally delete their logs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of entry IDs to mark",
                    },
                    "memories_created": {
                        "type": "integer",
                        "description": "Number of memories created from this batch",
                    },
                    "delete_logs": {
                        "type": "boolean",
                        "description": "Delete session log files after marking",
                        "default": True,
                    },
                },
                "required": ["entry_ids"],
            },
        ),
        # === Health Check ===
        Tool(
            name="ping",
            description="Health check endpoint.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


async def create_server(use_mock: bool = False) -> tuple[Server, dict[str, Any]]:
    """Create the CALM MCP server with all tools registered.

    Args:
        use_mock: If True, use MockEmbeddingService + MemoryStore (for tests).
                  If False, use real Qdrant + embedding models.

    Returns:
        Tuple of (Server, tool_registry). tool_registry maps tool names
        to their async implementation functions.
    """
    from calm import __version__
    from calm.ghap import ObservationCollector, ObservationPersister
    from calm.tools import (
        get_code_tools,
        get_context_tools,
        get_ghap_tools,
        get_git_tools,
        get_journal_tools,
        get_learning_tools,
        get_memory_tools,
    )

    server = Server("calm", version=__version__)

    # Service instances that may be set when using real services
    git_analyzer = None
    code_indexer = None
    experience_clusterer = None
    value_store_instance = None
    context_assembler = None

    vector_store: VectorStore
    semantic_embedder: EmbeddingService
    code_embedder: EmbeddingService

    if use_mock:
        from calm.embedding import MockEmbeddingService
        from calm.storage import MemoryStore

        vector_store = MemoryStore()
        semantic_embedder = MockEmbeddingService(dimension=384)
        code_embedder = MockEmbeddingService(dimension=384)
    else:
        # Lazy imports for fork safety (PyTorch must not load before fork)
        import os

        from calm.clustering import Clusterer, ExperienceClusterer
        from calm.context import ContextAssembler
        from calm.embedding.registry import EmbeddingRegistry
        from calm.indexers import CodeIndexer, TreeSitterParser
        from calm.search.searcher import Searcher
        from calm.storage.metadata import MetadataStore
        from calm.storage.qdrant import QdrantVectorStore
        from calm.values import ValueStore

        # Real vector store (Qdrant)
        vector_store = QdrantVectorStore(url=settings.qdrant_url)

        # Real embedders (loaded lazily on first embed() call)
        registry = EmbeddingRegistry(
            code_model=settings.code_model,
            semantic_model=settings.semantic_model,
        )
        semantic_embedder = registry.get_semantic_embedder()
        code_embedder = registry.get_code_embedder()

        # Metadata store (central SQLite DB)
        metadata_store = MetadataStore(settings.db_path)
        await metadata_store.initialize()

        # Code indexer (tree-sitter parser + batch embedding)
        parser = TreeSitterParser()
        code_indexer = CodeIndexer(
            parser=parser,
            embedding_service=code_embedder,
            vector_store=vector_store,
            metadata_store=metadata_store,
        )

        # Git analyzer (graceful fallback if not in a git repo)
        try:
            from calm.git import GitAnalyzer, GitPythonReader

            cwd = os.getcwd()
            git_reader = GitPythonReader(cwd)
            git_analyzer = GitAnalyzer(
                git_reader=git_reader,
                embedding_service=semantic_embedder,
                vector_store=vector_store,
                metadata_store=metadata_store,
            )
            logger.info("git_analyzer.initialized", repo_path=cwd)
        except Exception as e:
            logger.warning("git_analyzer.skipped", error=str(e))

        # Clustering
        clusterer = Clusterer()
        experience_clusterer = ExperienceClusterer(
            vector_store=vector_store,
            clusterer=clusterer,
        )

        # Value store
        value_store_instance = ValueStore(
            embedding_service=semantic_embedder,
            vector_store=vector_store,
            clusterer=experience_clusterer,
        )

        # Search + context assembly
        searcher = Searcher(
            embedding_service=semantic_embedder,
            vector_store=vector_store,
        )
        context_assembler = ContextAssembler(searcher=searcher)

    # Build tool registry
    tool_registry: dict[str, Any] = {}

    # Memory tools
    tool_registry.update(get_memory_tools(vector_store, semantic_embedder))

    # Code tools
    tool_registry.update(
        get_code_tools(vector_store, code_embedder, code_indexer=code_indexer)
    )

    # Git tools
    tool_registry.update(
        get_git_tools(vector_store, semantic_embedder, git_analyzer=git_analyzer)
    )

    # GHAP tools
    journal_dir = Path(settings.journal_dir)
    journal_dir.mkdir(parents=True, exist_ok=True)
    observation_collector = ObservationCollector(journal_dir)
    observation_persister = ObservationPersister(
        embedding_service=semantic_embedder,
        vector_store=vector_store,
    )
    tool_registry.update(get_ghap_tools(observation_collector, observation_persister))

    # Learning tools
    tool_registry.update(
        get_learning_tools(
            vector_store,
            semantic_embedder,
            experience_clusterer=experience_clusterer,
            value_store=value_store_instance,
        )
    )

    # Context tools
    tool_registry.update(
        get_context_tools(
            vector_store,
            semantic_embedder,
            context_assembler=context_assembler,
        )
    )

    # Journal tools
    tool_registry.update(get_journal_tools())

    # Ping tool
    async def ping() -> dict[str, Any]:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "server": "calm",
            "version": __version__,
        }

    tool_registry["ping"] = ping

    # Register the tool dispatcher - handles ALL tool calls
    @server.call_tool()  # type: ignore[misc]
    async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[Any]:
        """Dispatch tool calls to the appropriate implementation."""
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

    # Register list_tools handler - REQUIRED for clients to discover tools
    @server.list_tools()  # type: ignore[misc, no-untyped-call]
    async def handle_list_tools() -> list[Tool]:
        """Return all available tools with their schemas."""
        return _get_all_tool_definitions()

    logger.info("server.created", tool_count=len(tool_registry))

    return server, tool_registry
