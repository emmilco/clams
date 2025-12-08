"""Main entry point for the CLAMS server."""

import asyncio
import sys
from pathlib import Path

import structlog
from mcp.server import Server
from mcp.server.stdio import stdio_server

from clams.embedding import EmbeddingSettings, NomicEmbedding
from clams.server.config import ServerSettings
from clams.server.logging import configure_logging
from clams.server.tools import ServiceContainer, register_all_tools
from clams.storage.qdrant import QdrantVectorStore

logger = structlog.get_logger()


def create_embedding_service(settings: ServerSettings) -> NomicEmbedding:
    """Create the embedding service (loads model once).

    Args:
        settings: Server configuration

    Returns:
        Initialized NomicEmbedding service

    Raises:
        ValueError: If model loading fails
    """
    try:
        embedding_settings = EmbeddingSettings(model_name=settings.embedding_model)
        embedding_service = NomicEmbedding(settings=embedding_settings)
        logger.info("embedding_model.loaded", model=settings.embedding_model)
        return embedding_service
    except Exception as e:
        raise ValueError(
            f"Invalid embedding model '{settings.embedding_model}': {e}"
        ) from e


def validate_configuration(settings: ServerSettings) -> None:
    """Validate configuration before server start.

    Fails fast with clear error messages.

    Note: Embedding model validation happens separately in create_embedding_service().

    Args:
        settings: Server configuration

    Raises:
        ValueError: If configuration invalid
        ConnectionError: If Qdrant unreachable
    """
    # 1. Validate Qdrant connectivity (no tolerance per spec)
    try:
        import httpx
        response = httpx.get(f"{settings.qdrant_url}/collections", timeout=5.0)
        if response.status_code != 200:
            raise ConnectionError(
                f"Qdrant unreachable at {settings.qdrant_url}. "
                f"Status: {response.status_code}. "
                "Ensure Qdrant is running: docker run -p 6333:6333 qdrant/qdrant"
            )
    except httpx.ConnectError as e:
        raise ConnectionError(
            f"Cannot connect to Qdrant at {settings.qdrant_url}. "
            "Ensure Qdrant is running: docker run -p 6333:6333 qdrant/qdrant"
        ) from e
    except httpx.TimeoutException as e:
        raise ConnectionError(
            f"Qdrant connection timeout at {settings.qdrant_url}. "
            "Check network connectivity."
        ) from e

    # 2. Validate paths are writable
    for path_name, path_value in [
        ("storage_path", settings.storage_path),
        ("sqlite_path", settings.sqlite_path),
        ("journal_path", settings.journal_path),
    ]:
        path = Path(path_value).expanduser()
        parent = path.parent
        if not parent.exists():
            try:
                parent.mkdir(parents=True, exist_ok=True)
                logger.info("directory.created", path=str(parent))
            except Exception as e:
                raise ValueError(
                    f"{path_name} parent directory cannot be created: {parent}"
                ) from e
        if not parent.is_dir():
            raise ValueError(
                f"{path_name} parent is not a directory: {parent}"
            )

    # 3. Validate git repo if provided (optional - just log warning)
    if settings.repo_path:
        repo_path = Path(settings.repo_path).expanduser()
        if not repo_path.exists() or not (repo_path / ".git").exists():
            logger.warning(
                "git_repo.invalid",
                repo_path=settings.repo_path,
                note="Git analysis tools will not be available"
            )


async def initialize_collections(
    settings: ServerSettings,
    embedding_service: NomicEmbedding,
) -> None:
    """Ensure all required collections exist.

    Creates collections if they don't exist. Idempotent - safe to call
    multiple times.

    Args:
        settings: Server configuration
        embedding_service: Pre-initialized embedding service

    Raises:
        Exception: If collection creation fails or Qdrant is unreachable
    """
    vector_store = QdrantVectorStore(url=settings.qdrant_url)

    # Determine embedding dimension
    dimension = embedding_service.dimension

    # Define all required collections
    collections = [
        "memories",
        "code",
        "commits",
        "ghap_full",
        "ghap_strategy",
        "ghap_surprise",
        "ghap_root_cause",
        "values",
    ]

    # Create each collection (idempotent)
    for collection_name in collections:
        try:
            await vector_store.create_collection(
                name=collection_name,
                dimension=dimension,
                distance="cosine"
            )
            logger.info("collection.created", name=collection_name, dimension=dimension)
        except Exception as e:
            # Check if collection already exists (409 Conflict)
            if "already exists" in str(e) or "409" in str(e):
                logger.debug("collection.exists", name=collection_name)
            else:
                logger.error(
                    "collection.create_failed",
                    name=collection_name,
                    error=str(e),
                    exc_info=True
                )
                raise


async def create_server(
    settings: ServerSettings,
    embedding_service: NomicEmbedding,
) -> tuple[Server, ServiceContainer]:
    """Create and configure the MCP server.

    Args:
        settings: Server configuration
        embedding_service: Pre-initialized embedding service

    Returns:
        Tuple of (Server, ServiceContainer). Caller should call
        services.close() when done to release resources and prevent
        shutdown hangs.
    """
    server = Server("clams")

    # Register all tools
    services = await register_all_tools(server, settings, embedding_service)

    logger.info("server.created", server_name=server.name)
    return server, services


async def run_server(
    settings: ServerSettings,
    embedding_service: NomicEmbedding,
) -> None:
    """Run the MCP server.

    Args:
        settings: Server configuration
        embedding_service: Pre-initialized embedding service
    """
    logger.info("server.starting")

    # Initialize collections before accepting requests
    try:
        await initialize_collections(settings, embedding_service)
        logger.info("collections.initialized")
    except Exception as e:
        logger.error("collections.init_failed", error=str(e), exc_info=True)
        raise  # Fail fast - cannot proceed without storage

    # Create the server
    server, services = await create_server(settings, embedding_service)

    try:
        # Run using stdio transport
        async with stdio_server() as (read_stream, write_stream):
            logger.info("server.ready", transport="stdio")
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        # Clean up services to prevent process hang
        await services.close()
        logger.info("server.services_closed")


def main() -> None:
    """Entry point for the MCP server."""
    # Load configuration
    settings = ServerSettings()

    # Configure logging
    configure_logging(log_level=settings.log_level, log_format=settings.log_format)

    logger.info("clams.starting", version="0.1.0")

    # Validate configuration before starting (Qdrant, paths, git repo)
    try:
        validate_configuration(settings)
        logger.info("configuration.validated")
    except (ValueError, ConnectionError) as e:
        logger.error("configuration.invalid", error=str(e))
        sys.exit(1)

    # Create embedding service (loads model ONCE)
    try:
        embedding_service = create_embedding_service(settings)
    except ValueError as e:
        logger.error("embedding.invalid", error=str(e))
        sys.exit(1)

    try:
        # Run the async server
        asyncio.run(run_server(settings, embedding_service))
    except KeyboardInterrupt:
        logger.info("server.shutdown", reason="keyboard_interrupt")
    except Exception as e:
        logger.error("server.error", error=str(e), exc_info=True)
        raise


if __name__ == "__main__":
    main()
