"""MCP Protocol integration tests.

These tests verify the full MCP protocol flow as Claude Code would experience it:
1. Connect to server via stdio
2. Initialize session
3. Discover tools via list_tools
4. Call tools

This catches bugs where tools are implemented but not discoverable.
"""

import asyncio
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

pytest_plugins = ("pytest_asyncio",)

# Configure module-scoped event loop for async fixtures
# This allows all tests in this module to share a single server instance
# Also mark as integration tests (require external services)
pytestmark = [
    pytest.mark.asyncio(loop_scope="module"),
    pytest.mark.integration,
]

# Expected tools that should be discoverable
EXPECTED_TOOLS = {
    # Memory tools (SPEC-002-11)
    "store_memory",
    "retrieve_memories",
    "list_memories",
    "delete_memory",
    # Code tools (SPEC-002-11)
    "index_codebase",
    "search_code",
    "find_similar_code",
    # Git tools (SPEC-002-11)
    "search_commits",
    "get_file_history",
    "get_churn_hotspots",
    "get_code_authors",
    # GHAP tools (SPEC-002-15)
    "start_ghap",
    "update_ghap",
    "resolve_ghap",
    "get_active_ghap",
    "list_ghap_entries",
    # Learning tools (SPEC-002-15)
    "get_clusters",
    "get_cluster_members",
    "validate_value",
    "store_value",
    "list_values",
    # Search tools (SPEC-002-15)
    "search_experiences",
    # Health check
    "ping",
}


@pytest_asyncio.fixture(scope="module")
async def mcp_session() -> AsyncIterator[ClientSession]:
    """Create an MCP client session connected to the server.

    This fixture starts the actual server ONCE and all tests share it.
    Module scope dramatically improves test performance by avoiding
    repeated server startup (each takes ~5s for model loading).
    """
    import signal

    server_params = StdioServerParameters(
        command=".venv/bin/learning-memory-server",
        args=[],
    )

    # Use a more robust cleanup approach
    read_stream = None
    write_stream = None
    session = None

    try:
        ctx = stdio_client(server_params)
        read_stream, write_stream = await ctx.__aenter__()

        session = ClientSession(read_stream, write_stream)
        await session.__aenter__()

        # Initialize the session (MCP handshake)
        await session.initialize()

        yield session

    finally:
        # Cleanup in reverse order, ignoring errors
        if session is not None:
            try:
                await session.__aexit__(None, None, None)
            except Exception:
                pass  # Ignore cleanup errors

        if read_stream is not None:
            try:
                await ctx.__aexit__(None, None, None)
            except Exception:
                pass  # Ignore cleanup errors


class TestMCPProtocol:
    """Test MCP protocol-level behavior."""

    async def test_server_initializes(self, mcp_session: ClientSession) -> None:
        """Test that server completes MCP initialization handshake."""
        # If we get here, initialization succeeded
        # The fixture handles initialize() call
        assert mcp_session is not None

    async def test_tools_are_discoverable(self, mcp_session: ClientSession) -> None:
        """Test that all expected tools are returned by list_tools.

        This is the critical test that would have caught the missing
        @server.list_tools() handler bug.
        """
        tools_response = await mcp_session.list_tools()

        discovered_tools = {tool.name for tool in tools_response.tools}

        # Verify we got tools (not empty)
        assert len(discovered_tools) > 0, (
            "No tools discovered! Server is missing @server.list_tools() handler."
        )

        # Verify all expected tools are present
        missing_tools = EXPECTED_TOOLS - discovered_tools
        assert not missing_tools, (
            f"Missing tools: {missing_tools}. "
            f"Discovered: {discovered_tools}"
        )

        # Log any extra tools (not an error, just informational)
        extra_tools = discovered_tools - EXPECTED_TOOLS
        if extra_tools:
            print(f"Note: Found additional tools not in expected set: {extra_tools}")

    async def test_tools_have_valid_schemas(self, mcp_session: ClientSession) -> None:
        """Test that all tools have proper input schemas defined."""
        tools_response = await mcp_session.list_tools()

        for tool in tools_response.tools:
            # Every tool should have a name
            assert tool.name, "Tool missing name"

            # Every tool should have a description
            assert tool.description, f"Tool {tool.name} missing description"

            # Every tool should have an input schema
            assert tool.inputSchema is not None, (
                f"Tool {tool.name} missing inputSchema"
            )

            # Input schema should be a valid JSON Schema object
            assert isinstance(tool.inputSchema, dict), (
                f"Tool {tool.name} inputSchema is not a dict"
            )
            assert tool.inputSchema.get("type") == "object", (
                f"Tool {tool.name} inputSchema type should be 'object'"
            )

    async def test_ping_tool_callable(self, mcp_session: ClientSession) -> None:
        """Test that the ping tool can be called and returns expected response."""
        result = await mcp_session.call_tool("ping", {})

        # Ping should return "pong"
        assert result is not None
        assert len(result.content) > 0

        # Check the response content
        content = result.content[0]
        assert content.type == "text"
        assert "pong" in content.text.lower()

    async def test_store_memory_callable(self, mcp_session: ClientSession) -> None:
        """Test that store_memory tool can be called with valid inputs."""
        result = await mcp_session.call_tool(
            "store_memory",
            {
                "content": "Test memory from MCP protocol test",
                "category": "fact",
                "importance": 0.5,
                "tags": ["test", "mcp-protocol"],
            },
        )

        assert result is not None
        assert len(result.content) > 0

        # Response should contain the stored memory ID
        content = result.content[0]
        assert content.type == "text"
        # The response is JSON, should contain "id" field
        assert "id" in content.text

    async def test_retrieve_memories_callable(
        self, mcp_session: ClientSession
    ) -> None:
        """Test that retrieve_memories tool can be called."""
        result = await mcp_session.call_tool(
            "retrieve_memories",
            {
                "query": "test memory",
                "limit": 5,
            },
        )

        assert result is not None
        assert len(result.content) > 0

    async def test_get_active_ghap_callable(self, mcp_session: ClientSession) -> None:
        """Test that get_active_ghap tool can be called."""
        result = await mcp_session.call_tool("get_active_ghap", {})

        assert result is not None
        assert len(result.content) > 0

        # Response should indicate whether there's an active GHAP
        content = result.content[0]
        assert content.type == "text"
        assert "has_active" in content.text

    async def test_search_experiences_callable(
        self, mcp_session: ClientSession
    ) -> None:
        """Test that search_experiences tool can be called."""
        result = await mcp_session.call_tool(
            "search_experiences",
            {
                "query": "debugging",
                "axis": "full",
                "limit": 5,
            },
        )

        assert result is not None
        assert len(result.content) > 0


class TestMCPToolDiscoveryRegression:
    """Regression tests for tool discovery bugs."""

    async def test_list_tools_returns_nonzero(
        self, mcp_session: ClientSession
    ) -> None:
        """Regression test: list_tools must return at least one tool.

        This test exists because we had a bug where @server.list_tools()
        handler was missing, causing Claude Code to see 0 tools.
        """
        tools_response = await mcp_session.list_tools()

        assert len(tools_response.tools) > 0, (
            "REGRESSION: list_tools returned 0 tools! "
            "Check that @server.list_tools() handler is registered."
        )

    async def test_tool_count_matches_expected(
        self, mcp_session: ClientSession
    ) -> None:
        """Test that tool count is in expected range.

        This catches both missing tools and accidental duplicates.
        """
        tools_response = await mcp_session.list_tools()
        tool_count = len(tools_response.tools)

        # We expect 23 tools (22 functional + 1 ping)
        expected_count = len(EXPECTED_TOOLS)

        assert tool_count >= expected_count, (
            f"Too few tools: got {tool_count}, expected at least {expected_count}"
        )

        # Allow some buffer for future tools, but catch major issues
        assert tool_count <= expected_count + 10, (
            f"Unexpectedly many tools: got {tool_count}, expected ~{expected_count}"
        )
