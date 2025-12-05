"""Main entry point for the Learning Memory Server."""

import asyncio
import sys
from pathlib import Path

import structlog
from mcp.server import Server
from mcp.server.stdio import stdio_server

from learning_memory_server.embedding import EmbeddingSettings, NomicEmbedding
from learning_memory_server.server.config import ServerSettings
from learning_memory_server.server.logging import configure_logging
from learning_memory_server.server.tools import register_all_tools
from learning_memory_server.storage.qdrant import QdrantVectorStore

logger = structlog.get_logger()


def validate_configuration(settings: ServerSettings) -> None:
    """Validate configuration before server start.

    Fails fast with clear error messages.

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

    # 2. Validate embedding model (will fail on first embed if invalid)
    try:
        from sentence_transformers import SentenceTransformer
        # Try to load model (downloads if needed)
        _ = SentenceTransformer(settings.embedding_model, trust_remote_code=True)
        logger.info("embedding_model.validated", model=settings.embedding_model)
    except Exception as e:
        raise ValueError(
            f"Invalid embedding model '{settings.embedding_model}': {e}"
        ) from e

    # 3. Validate paths are writable
    for path_name, path_value in [
        ("storage_path", settings.storage_path),
        ("sqlite_path", settings.sqlite_path),
        ("journal_path", settings.journal_path),
    ]:
        path = Path(path_value)
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

    # 4. Validate git repo if provided (optional - just log warning)
    if settings.repo_path:
        repo_path = Path(settings.repo_path)
        if not repo_path.exists() or not (repo_path / ".git").exists():
            logger.warning(
                "git_repo.invalid",
                repo_path=settings.repo_path,
                note="Git analysis tools will not be available"
            )


async def initialize_collections(settings: ServerSettings) -> None:
    """Ensure all required collections exist.

    Creates collections if they don't exist. Idempotent - safe to call
    multiple times.

    Args:
        settings: Server configuration

    Raises:
        Exception: If collection creation fails or Qdrant is unreachable
    """
    # Initialize services
    embedding_settings = EmbeddingSettings(model_name=settings.embedding_model)
    embedding_service = NomicEmbedding(settings=embedding_settings)
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
        except ValueError:
            # Collection already exists - this is normal
            logger.debug("collection.exists", name=collection_name)
        except Exception as e:
            logger.error(
                "collection.create_failed",
                name=collection_name,
                error=str(e),
                exc_info=True
            )
            raise


def create_server(settings: ServerSettings) -> Server:
    """Create and configure the MCP server.

    Args:
        settings: Server configuration

    Returns:
        Configured MCP Server instance
    """
    server = Server("learning-memory-server")

    # Register all tools
    register_all_tools(server, settings)

    logger.info("server.created", server_name=server.name)
    return server


async def run_server(settings: ServerSettings) -> None:
    """Run the MCP server.

    Args:
        settings: Server configuration
    """
    logger.info("server.starting")

    # Initialize collections before accepting requests
    try:
        await initialize_collections(settings)
        logger.info("collections.initialized")
    except Exception as e:
        logger.error("collections.init_failed", error=str(e), exc_info=True)
        raise  # Fail fast - cannot proceed without storage

    # Create the server
    server = create_server(settings)

    # Run using stdio transport
    async with stdio_server() as (read_stream, write_stream):
        logger.info("server.ready", transport="stdio")
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """Entry point for the MCP server."""
    # Load configuration
    settings = ServerSettings()

    # Configure logging
    configure_logging(log_level=settings.log_level, log_format=settings.log_format)

    logger.info("learning_memory_server.starting", version="0.1.0")

    # Validate configuration before starting
    try:
        validate_configuration(settings)
        logger.info("configuration.validated")
    except (ValueError, ConnectionError) as e:
        logger.error("configuration.invalid", error=str(e))
        sys.exit(1)

    try:
        # Run the async server
        asyncio.run(run_server(settings))
    except KeyboardInterrupt:
        logger.info("server.shutdown", reason="keyboard_interrupt")
    except Exception as e:
        logger.error("server.error", error=str(e), exc_info=True)
        raise


if __name__ == "__main__":
    main()
