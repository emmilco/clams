"""MCP tool implementations and service container."""

from dataclasses import dataclass
from pathlib import Path

import structlog
from mcp.server import Server

from learning_memory_server.clustering import ExperienceClusterer
from learning_memory_server.embedding import (
    EmbeddingService,
    EmbeddingSettings,
    NomicEmbedding,
)
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
    if settings.repo_path:
        try:
            from learning_memory_server.git import (
                GitAnalyzer,
                GitPythonReader,
            )
            git_reader = GitPythonReader(repo_path=settings.repo_path)
            git_analyzer = GitAnalyzer(
                git_reader=git_reader,
                embedding_service=embedding_service,
                vector_store=vector_store,
                metadata_store=metadata_store,
            )
            logger.info("git.initialized", repo_path=settings.repo_path)
        except ImportError as e:
            logger.warning("git.init_skipped", reason="module_not_found", error=str(e))
        except Exception as e:
            logger.warning(
                "git.init_failed", repo_path=settings.repo_path, error=str(e)
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
        journal_dir=Path(settings.journal_path),
    )
    observation_persister = ObservationPersister(
        embedding_service=services.embedding_service,
        vector_store=services.vector_store,
    )
    register_ghap_tools(server, observation_collector, observation_persister)

    # Initialize and register learning tools (from SPEC-002-15)
    experience_clusterer = ExperienceClusterer(
        vector_store=services.vector_store,
        clusterer=None,  # type: ignore[arg-type]  # Will be initialized when needed
    )
    value_store = ValueStore(
        embedding_service=services.embedding_service,
        vector_store=services.vector_store,
        clusterer=None,  # type: ignore[arg-type]  # Will be initialized when needed
    )
    register_learning_tools(server, experience_clusterer, value_store)

    # Initialize and register search tools (from SPEC-002-15)
    searcher = Searcher(
        embedding_service=services.embedding_service,
        vector_store=services.vector_store,
    )
    register_search_tools(server, searcher)

    # Register ping tool for health checks
    @server.call_tool()  # type: ignore[untyped-decorator]
    async def ping() -> str:
        """Health check endpoint.

        Returns:
            Status message
        """
        return "pong"

    logger.info(
        "tools.registered",
        has_code=services.code_indexer is not None,
        has_git=services.git_analyzer is not None,
        has_searcher=services.searcher is not None,
    )
