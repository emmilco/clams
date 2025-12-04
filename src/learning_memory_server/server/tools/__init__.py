"""MCP tool implementations and service container."""

from dataclasses import dataclass

import structlog
from mcp.server import Server

from learning_memory_server.embedding import (
    EmbeddingService,
    EmbeddingSettings,
    NomicEmbedding,
)
from learning_memory_server.server.config import ServerSettings
from learning_memory_server.storage import VectorStore
from learning_memory_server.storage.metadata import MetadataStore
from learning_memory_server.storage.qdrant import QdrantVectorStore

logger = structlog.get_logger()


@dataclass
class ServiceContainer:
    """Container for shared services used by MCP tools.

    Services that depend on incomplete specs (SPEC-002-06, 07, 09) are optional
    and initialized lazily when needed.
    """

    embedding_service: EmbeddingService
    vector_store: VectorStore
    metadata_store: MetadataStore
    code_indexer: object | None = None  # Will be CodeIndexer when SPEC-002-06 complete
    git_analyzer: object | None = None  # Will be GitAnalyzer when SPEC-002-07 complete
    searcher: object | None = None  # Will be Searcher when SPEC-002-09 complete


def initialize_services(settings: ServerSettings) -> ServiceContainer:
    """Initialize all services for MCP tools.

    Core services (embedding, vector, metadata) are always initialized.
    Optional services (code, git, search) are only initialized if their
    dependencies (SPEC-002-06, 07, 09) are complete.

    Args:
        settings: Server configuration

    Returns:
        ServiceContainer with initialized services
    """
    logger.info("services.initializing")

    # Core infrastructure (always available)
    embedding_settings = EmbeddingSettings(model_name=settings.embedding_model)
    embedding_service = NomicEmbedding(settings=embedding_settings)
    vector_store = QdrantVectorStore(url=settings.qdrant_url)
    metadata_store = MetadataStore(db_path=settings.sqlite_path)

    # Code indexing (optional - depends on SPEC-002-06)
    code_indexer = None
    # TODO: Enable when SPEC-002-06 complete
    # try:
    #     from learning_memory_server.indexers import (
    #         CodeIndexer,
    #         TreeSitterParser,
    #     )
    #     code_parser = TreeSitterParser()
    #     code_indexer = CodeIndexer(
    #         parser=code_parser,
    #         embedding_service=embedding_service,
    #         vector_store=vector_store,
    #         metadata_store=metadata_store,
    #     )
    #     logger.info("code.initialized")
    # except Exception as e:
    #     logger.warning("code.init_failed", error=str(e))

    # Git analysis (optional - depends on SPEC-002-07)
    git_analyzer = None
    # TODO: Enable when SPEC-002-07 complete
    # if settings.repo_path:
    #     try:
    #         from learning_memory_server.indexers.git import (
    #             GitAnalyzer,
    #             GitPythonReader,
    #         )
    #         git_reader = GitPythonReader(repo_path=settings.repo_path)
    #         git_analyzer = GitAnalyzer(
    #             git_reader=git_reader,
    #             embedding_service=embedding_service,
    #             vector_store=vector_store,
    #             metadata_store=metadata_store,
    #         )
    #         logger.info("git.initialized", repo_path=settings.repo_path)
    #     except Exception as e:
    #         logger.warning("git.init_failed", error=str(e))

    # Search service (optional - depends on SPEC-002-09)
    searcher = None
    # TODO: Enable when SPEC-002-09 complete
    # try:
    #     from learning_memory_server.search import Searcher
    #     searcher = Searcher(
    #         embedding_service=embedding_service,
    #         vector_store=vector_store,
    #     )
    #     logger.info("searcher.initialized")
    # except Exception as e:
    #     logger.warning("searcher.init_failed", error=str(e))

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


def register_all_tools(server: Server, settings: ServerSettings) -> None:
    """Register all MCP tools with the server.

    Args:
        server: MCP Server instance
        settings: Server configuration
    """
    # Initialize shared services
    services = initialize_services(settings)

    # Import and register tool modules
    from .code import register_code_tools
    from .git import register_git_tools
    from .memory import register_memory_tools

    register_memory_tools(server, services)
    register_code_tools(server, services)
    register_git_tools(server, services)

    # Register ping tool for health checks
    @server.call_tool()  # type: ignore[no-untyped-call, misc]
    async def ping() -> str:
        """Health check endpoint.

        Returns:
            Status message
        """
        return "pong"

    logger.info("tools.registered")
