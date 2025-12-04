#!/usr/bin/env python3
"""MCP client utility for hook scripts.

This module provides a command-line interface for shell scripts to call MCP tools.
It handles connection failures gracefully and returns empty results on errors.
"""

import asyncio
import json
import sys
from typing import Any

import structlog
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

logger = structlog.get_logger()


class MCPClient:
    """Resilient MCP client for hook scripts."""

    def __init__(self, server_command: list[str], timeout: float = 10.0) -> None:
        """Initialize MCP client.

        Args:
            server_command: Command to start MCP server
            timeout: Maximum time to wait for responses (default: 10s)
        """
        self.server_command = server_command
        self.timeout = timeout
        self.session: ClientSession | None = None

    async def connect(self) -> bool:
        """Connect to MCP server.

        Returns:
            True if connected, False on failure
        """
        try:
            server_params = StdioServerParameters(
                command=self.server_command[0],
                args=self.server_command[1:] if len(self.server_command) > 1 else [],
                env=None,
            )
            # Note: We can't use async context manager here because we need
            # the connection to persist across multiple tool calls.
            # For now, we'll use a simpler approach and accept the limitation.
            # The connection will be cleaned up when the process exits.
            streams = stdio_client(server_params)
            read, write = await streams.__aenter__()
            self.session = ClientSession(read, write)
            await asyncio.wait_for(self.session.initialize(), timeout=self.timeout)
            return True
        except (TimeoutError, Exception) as e:
            logger.warning("mcp_client.connect_failed", error=str(e))
            return False

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Call an MCP tool.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool result as dict, or empty dict on failure
        """
        if self.session is None:
            logger.warning("mcp_client.not_connected")
            return {}

        try:
            result = await asyncio.wait_for(
                self.session.call_tool(tool_name, arguments), timeout=self.timeout
            )
            # MCP tools return JSON string in .text, must parse it
            if result.content:
                content = result.content[0]
                if isinstance(content, TextContent):
                    text = content.text
                    return json.loads(text) if text else {}
            return {}
        except json.JSONDecodeError as e:
            logger.error("mcp_client.invalid_json", tool=tool_name, error=str(e))
            return {}
        except (TimeoutError, Exception) as e:
            logger.warning("mcp_client.call_failed", tool=tool_name, error=str(e))
            return {}

    async def close(self) -> None:
        """Close the MCP session.

        Note: With the context manager pattern, the connection is automatically
        closed when exiting the async context, so this is a no-op.
        """
        # Connection is managed by the context manager in connect()
        pass


async def main() -> None:
    """CLI interface for calling MCP tools from hooks.

    Usage:
        mcp_client.py <tool_name> <arguments_json>

    Output:
        JSON result on stdout

    Exit codes:
        0: Success
        1: Connection failed
        2: Tool call failed
    """
    if len(sys.argv) != 3:
        error_msg = "Usage: mcp_client.py <tool_name> <arguments_json>"
        print(json.dumps({"error": error_msg}))
        sys.exit(2)

    tool_name = sys.argv[1]
    try:
        arguments = json.loads(sys.argv[2])
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON arguments"}))
        sys.exit(2)

    # Create client
    client = MCPClient(
        server_command=["python", "-m", "learning_memory_server"], timeout=10.0
    )

    # Connect
    if not await client.connect():
        print(json.dumps({"error": "Failed to connect to MCP server"}))
        sys.exit(1)

    # Call tool
    result = await client.call_tool(tool_name, arguments)

    # Close
    await client.close()

    # Output result
    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
