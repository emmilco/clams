"""Main entry point for the Learning Memory Server."""

import asyncio
import sys
from pathlib import Path

import structlog
from mcp.server import Server
from mcp.server.stdio import stdio_server

from learning_memory_server.embedding import initialize_registry
from learning_memory_server.server.config import ServerSettings
from learning_memory_server.server.logging import configure_logging
from learning_memory_server.server.tools import ServiceContainer, register_all_tools

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


async def create_server(
    settings: ServerSettings,
) -> tuple[Server, ServiceContainer]:
    """Create and configure the MCP server.

    Args:
        settings: Server configuration

    Returns:
        Tuple of (Server, ServiceContainer). Caller should call
        services.close() when done to release resources and prevent
        shutdown hangs.
    """
    from learning_memory_server.embedding import get_code_embedder, get_semantic_embedder

    server = Server("learning-memory-server")

    # Get embedders from registry (loads lazily when first tool calls them)
    code_embedder = get_code_embedder()
    semantic_embedder = get_semantic_embedder()

    # Register all tools
    services = await register_all_tools(
        server, settings, code_embedder, semantic_embedder
    )

    logger.info("server.created", server_name=server.name)
    return server, services


async def run_server(settings: ServerSettings) -> None:
    """Run the MCP server.

    Args:
        settings: Server configuration
    """
    logger.info("server.starting")

    # Create the server
    server, services = await create_server(settings)

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

    logger.info("learning_memory_server.starting", version="0.1.0")

    # Validate configuration before starting (Qdrant, paths, git repo)
    try:
        validate_configuration(settings)
        logger.info("configuration.validated")
    except (ValueError, ConnectionError) as e:
        logger.error("configuration.invalid", error=str(e))
        sys.exit(1)

    # Initialize embedding registry (does NOT load models)
    initialize_registry(settings.code_model, settings.semantic_model)
    logger.info("embedding_registry.initialized")

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
