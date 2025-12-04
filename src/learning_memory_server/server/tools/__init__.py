"""MCP tool implementations."""

import structlog
from mcp.server import Server

from learning_memory_server.server.config import ServerSettings

logger = structlog.get_logger()


def register_all_tools(server: Server, settings: ServerSettings) -> None:
    """Register all MCP tools with the server.

    Args:
        server: MCP Server instance
        settings: Server configuration
    """
    # Register ping tool for health checks
    @server.call_tool()  # type: ignore[untyped-decorator]
    async def ping() -> str:
        """Health check endpoint.

        Returns:
            Status message
        """
        return "pong"

    logger.info("tools.registered", tool_count=1)
