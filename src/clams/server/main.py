"""Main entry point for the CLAMS server.

IMPORTANT: This module minimizes imports at module level to allow fast
argument parsing. Heavy imports (PyTorch, embedding models) are deferred
to _run_server() which is only called after daemon spawning completes.
"""

import argparse
import sys
from typing import Any


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments with transport mode and options
    """
    parser = argparse.ArgumentParser(
        description="CLAMS MCP Server - semantic code search and memory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  clams-server                          # Run with stdio transport (default)
  clams-server --http                   # Run with HTTP transport on port 6334
  clams-server --http --port 8080       # Run with HTTP transport on port 8080
  clams-server --daemon                 # Run as background daemon (HTTP mode)
  clams-server --stop                   # Stop running daemon
""",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Run with HTTP+SSE transport (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="HTTP server host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=6334,
        help="HTTP server port (default: 6334)",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as background daemon (implies --http)",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop running daemon and exit",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for the MCP server.

    This function handles daemon/stop commands BEFORE importing heavy modules
    to avoid MPS fork safety issues on macOS. PyTorch initializes MPS on import,
    and os.fork() crashes if MPS was initialized in the parent process.
    """
    args = parse_args()

    # Handle --stop command (no heavy imports needed)
    if args.stop:
        from clams.server.http import stop_server
        if stop_server():
            print("Server stopped")
        else:
            print("Server was not running")
        return

    # Handle --daemon: fork BEFORE importing PyTorch
    if args.daemon:
        from clams.server.http import daemonize, is_server_running

        if is_server_running():
            print("Server is already running")
            return

        # Fork into background - this MUST happen before PyTorch import
        daemonize()

    # NOW it's safe to import heavy modules (PyTorch, embeddings, etc.)
    # In daemon mode, we're in the child process after fork
    _run_server(args)


def _run_server(args: argparse.Namespace) -> None:
    """Run the server after daemonization (if applicable).

    This function contains all the heavy imports and actual server logic.
    It's separated from main() to ensure imports happen after fork().
    """
    import asyncio
    import errno
    from pathlib import Path
    from typing import Any

    import structlog
    from mcp.server import Server
    from mcp.server.stdio import stdio_server

    from clams.embedding import initialize_registry
    from clams.server.config import ServerSettings
    from clams.server.logging import configure_logging
    from clams.server.tools import ServiceContainer, register_all_tools

    logger = structlog.get_logger()

    # Load configuration
    settings = ServerSettings()

    # Configure logging
    configure_logging(log_level=settings.log_level, log_format=settings.log_format)

    # Determine transport mode
    use_http = args.http or args.daemon
    transport_mode = "http" if use_http else "stdio"

    logger.info("clams.starting", version="0.1.0", transport=transport_mode)

    # Validate configuration before starting (Qdrant, paths, git repo)
    try:
        _validate_configuration(settings, logger)
        logger.info("configuration.validated")
    except (ValueError, ConnectionError) as e:
        logger.error("configuration.invalid", error=str(e))
        sys.exit(1)

    # Initialize embedding registry (does NOT load models)
    initialize_registry(settings.code_model, settings.semantic_model)
    logger.info("embedding_registry.initialized")

    try:
        if use_http:
            asyncio.run(_run_http_server(settings, args.host, args.port, logger))
        else:
            asyncio.run(_run_stdio_server(settings, logger))
    except KeyboardInterrupt:
        logger.info("server.shutdown", reason="keyboard_interrupt")
    except Exception as e:
        logger.error("server.error", error=str(e), exc_info=True)
        raise


def _validate_configuration(settings: "ServerSettings", logger: Any) -> None:
    """Validate configuration before server start.

    Fails fast with clear error messages.

    Args:
        settings: Server configuration
        logger: Structlog logger

    Raises:
        ValueError: If configuration invalid
        ConnectionError: If Qdrant unreachable
    """
    from pathlib import Path

    import httpx

    # 1. Validate Qdrant connectivity (no tolerance per spec)
    try:
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


async def _run_stdio_server(settings: "ServerSettings", logger: Any) -> None:
    """Run the MCP server with stdio transport.

    Args:
        settings: Server configuration
        logger: Structlog logger
    """
    from mcp.server.stdio import stdio_server

    logger.info("server.starting")

    # Create the server (tool_registry not needed for stdio transport)
    server, services, _tool_registry = await create_server(settings)

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


async def _run_http_server(
    settings: "ServerSettings",
    host: str,
    port: int,
    logger: Any,
) -> None:
    """Run the MCP server with HTTP+SSE transport.

    Args:
        settings: Server configuration
        host: HTTP server host
        port: HTTP server port
        logger: Structlog logger
    """
    import errno

    from clams.server.http import HttpServer

    logger.info("server.starting", transport="http", host=host, port=port)

    # Create the server
    server, services, tool_registry = await create_server(settings)

    # Wrap in HTTP server with tool registry for direct API calls
    http_server = HttpServer(server, services, tool_registry, host=host, port=port)

    try:
        await http_server.run()
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            logger.error(
                "server.port_in_use",
                port=port,
                error=f"Port {port} is already in use. "
                f"Use --port to specify a different port.",
            )
            sys.exit(1)
        raise


async def create_server(
    settings: "ServerSettings",
) -> tuple["Server", "ServiceContainer", dict[str, Any]]:
    """Create and configure the MCP server.

    Args:
        settings: Server configuration

    Returns:
        Tuple of (Server, ServiceContainer, tool_registry). Caller should call
        services.close() when done to release resources and prevent
        shutdown hangs. tool_registry maps tool names to async functions.
    """
    from typing import Any

    import structlog
    from mcp.server import Server

    from clams.embedding import (
        get_code_embedder,
        get_semantic_embedder,
    )
    from clams.server.tools import register_all_tools

    logger = structlog.get_logger()

    server = Server("clams")

    # Pass accessor functions to tools - embedders load lazily on first use
    # Do NOT call get_code_embedder() here - that would load models at startup
    # Tools call the accessor functions when they actually need embeddings
    services, tool_registry = await register_all_tools(
        server, settings, get_code_embedder, get_semantic_embedder
    )

    logger.info("server.created", server_name=server.name)
    return server, services, tool_registry


if __name__ == "__main__":
    main()
