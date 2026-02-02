"""CALM MCP Server application.

This module provides the MCP server skeleton for CALM.
Tools will be registered in later phases.
"""

from typing import Any

from mcp.server import Server


def create_server() -> Server:
    """Create the CALM MCP server.

    Returns:
        Configured MCP Server instance with basic tools registered.
    """
    server = Server("calm")

    @server.tool()  # type: ignore[attr-defined, misc]
    async def ping() -> dict[str, Any]:
        """Health check endpoint.

        Returns server status information.
        """
        from calm import __version__
        return {
            "status": "healthy",
            "server": "calm",
            "version": __version__,
        }

    return server
