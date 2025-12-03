"""Main entry point for the Learning Memory Server."""

import asyncio

import structlog
from mcp.server import Server
from mcp.server.stdio import stdio_server

from learning_memory_server.server.config import ServerSettings
from learning_memory_server.server.logging import configure_logging
from learning_memory_server.server.tools import register_all_tools

logger = structlog.get_logger()


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
