"""Tests for MCP client utility."""

import asyncio
import json

# Import the module under test
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from mcp import ClientSession
from mcp.types import CallToolResult, TextContent

# Add clams/ to path for importing
clams_dir = Path(__file__).parent.parent.parent / "clams"
sys.path.insert(0, str(clams_dir))

from mcp_client import MCPClient  # noqa: E402


class TestMCPClient:
    """Test suite for MCPClient."""

    @pytest.mark.asyncio
    async def test_init(self) -> None:
        """Test MCPClient initialization."""
        client = MCPClient([".venv/bin/clams-server"], timeout=5.0)
        assert client.server_command == [".venv/bin/clams-server"]
        assert client.timeout == 5.0
        assert client.session is None

    @pytest.mark.asyncio
    async def test_connect_success(self) -> None:
        """Test successful connection to MCP server."""
        client = MCPClient(["mock-server"], timeout=5.0)

        # Mock stdio_client and session
        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_session = AsyncMock(spec=ClientSession)

        with patch("mcp_client.stdio_client") as mock_stdio:
            with patch("mcp_client.ClientSession") as mock_session_cls:
                # stdio_client returns a context manager
                mock_context_mgr = AsyncMock()
                mock_context_mgr.__aenter__ = AsyncMock(
                    return_value=(mock_read, mock_write)
                )
                mock_stdio.return_value = mock_context_mgr
                mock_session_cls.return_value = mock_session

                result = await client.connect()

                assert result is True
                assert client.session is not None
                mock_session.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_timeout(self) -> None:
        """Test connection timeout handling."""
        client = MCPClient(["sleep", "100"], timeout=0.1)

        with patch("mcp_client.stdio_client") as mock_stdio:
            # Simulate timeout by making stdio_client sleep
            async def slow_connect() -> tuple[Any, Any]:
                await asyncio.sleep(10)
                return (AsyncMock(), AsyncMock())

            mock_stdio.side_effect = slow_connect

            result = await client.connect()

            assert result is False
            assert client.session is None

    @pytest.mark.asyncio
    async def test_connect_exception(self) -> None:
        """Test connection exception handling."""
        client = MCPClient(["invalid-command"], timeout=5.0)

        with patch("mcp_client.stdio_client") as mock_stdio:
            mock_stdio.side_effect = Exception("Connection failed")

            result = await client.connect()

            assert result is False
            assert client.session is None

    @pytest.mark.asyncio
    async def test_call_tool_not_connected(self) -> None:
        """Test call_tool when not connected."""
        client = MCPClient(["mock-server"], timeout=5.0)

        result = await client.call_tool("test_tool", {})

        assert result == {}

    @pytest.mark.asyncio
    async def test_call_tool_success(self) -> None:
        """Test successful tool call."""
        client = MCPClient(["mock-server"], timeout=5.0)

        # Mock session
        mock_session = AsyncMock(spec=ClientSession)
        client.session = mock_session

        # Create mock result with JSON string in text
        expected_data = {"message": "pong", "status": "ok"}
        mock_result = CallToolResult(
            content=[TextContent(type="text", text=json.dumps(expected_data))]
        )
        mock_session.call_tool.return_value = mock_result

        result = await client.call_tool("ping", {"arg": "value"})

        assert result == expected_data
        mock_session.call_tool.assert_called_once_with("ping", {"arg": "value"})

    @pytest.mark.asyncio
    async def test_call_tool_empty_content(self) -> None:
        """Test tool call with empty content."""
        client = MCPClient(["mock-server"], timeout=5.0)

        # Mock session
        mock_session = AsyncMock(spec=ClientSession)
        client.session = mock_session

        # Create mock result with empty content
        mock_result = CallToolResult(content=[])
        mock_session.call_tool.return_value = mock_result

        result = await client.call_tool("test_tool", {})

        assert result == {}

    @pytest.mark.asyncio
    async def test_call_tool_invalid_json(self) -> None:
        """Test tool call with invalid JSON response."""
        client = MCPClient(["mock-server"], timeout=5.0)

        # Mock session
        mock_session = AsyncMock(spec=ClientSession)
        client.session = mock_session

        # Create mock result with invalid JSON
        mock_result = CallToolResult(
            content=[TextContent(type="text", text="not valid json")]
        )
        mock_session.call_tool.return_value = mock_result

        result = await client.call_tool("test_tool", {})

        assert result == {}

    @pytest.mark.asyncio
    async def test_call_tool_timeout(self) -> None:
        """Test tool call timeout."""
        client = MCPClient(["mock-server"], timeout=0.1)

        # Mock session
        mock_session = AsyncMock(spec=ClientSession)
        client.session = mock_session

        # Simulate slow tool call
        async def slow_call(*args: Any, **kwargs: Any) -> CallToolResult:
            await asyncio.sleep(10)
            return CallToolResult(content=[])

        mock_session.call_tool.side_effect = slow_call

        result = await client.call_tool("slow_tool", {})

        assert result == {}

    @pytest.mark.asyncio
    async def test_call_tool_exception(self) -> None:
        """Test tool call exception handling."""
        client = MCPClient(["mock-server"], timeout=5.0)

        # Mock session
        mock_session = AsyncMock(spec=ClientSession)
        client.session = mock_session

        # Simulate exception
        mock_session.call_tool.side_effect = Exception("Tool call failed")

        result = await client.call_tool("test_tool", {})

        assert result == {}

    @pytest.mark.asyncio
    async def test_close_with_session(self) -> None:
        """Test closing with active session.

        Note: close() is now a no-op since the connection is managed by
        the context manager in connect() and will be cleaned up automatically.
        """
        client = MCPClient(["mock-server"], timeout=5.0)

        # Mock session
        mock_session = AsyncMock()
        client.session = mock_session

        # Should not raise exception (close is a no-op)
        await client.close()

    @pytest.mark.asyncio
    async def test_close_without_session(self) -> None:
        """Test closing without session."""
        client = MCPClient(["mock-server"], timeout=5.0)

        # Should not raise exception
        await client.close()


class TestMainCLI:
    """Test suite for main CLI interface."""

    def test_main_invalid_args(self, capsys: Any) -> None:
        """Test main with invalid number of arguments."""
        with patch("sys.argv", ["mcp_client.py"]):
            with pytest.raises(SystemExit) as exc_info:
                from mcp_client import main

                asyncio.run(main())

            assert exc_info.value.code == 2
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert "error" in output
            assert "Usage" in output["error"]

    def test_main_invalid_json_args(self, capsys: Any) -> None:
        """Test main with invalid JSON arguments."""
        with patch("sys.argv", ["mcp_client.py", "tool_name", "not json"]):
            with pytest.raises(SystemExit) as exc_info:
                from mcp_client import main

                asyncio.run(main())

            assert exc_info.value.code == 2
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert "error" in output
            assert "Invalid JSON" in output["error"]

    @pytest.mark.asyncio
    async def test_main_connection_failed(self, capsys: Any) -> None:
        """Test main when connection fails."""
        with patch("sys.argv", ["mcp_client.py", "test_tool", "{}"]):
            with patch("mcp_client.MCPClient.connect") as mock_connect:
                mock_connect.return_value = False

                with pytest.raises(SystemExit) as exc_info:
                    from mcp_client import main

                    await main()

                assert exc_info.value.code == 1
                captured = capsys.readouterr()
                output = json.loads(captured.out)
                assert "error" in output

    @pytest.mark.asyncio
    async def test_main_success(self, capsys: Any) -> None:
        """Test main with successful tool call."""
        expected_result = {"status": "ok", "data": "test"}

        with patch("sys.argv", ["mcp_client.py", "test_tool", '{"arg": "value"}']):
            with patch("mcp_client.MCPClient.connect") as mock_connect:
                with patch("mcp_client.MCPClient.call_tool") as mock_call:
                    with patch("mcp_client.MCPClient.close") as mock_close:
                        mock_connect.return_value = True
                        mock_call.return_value = expected_result

                        with pytest.raises(SystemExit) as exc_info:
                            from mcp_client import main

                            await main()

                        assert exc_info.value.code == 0
                        captured = capsys.readouterr()
                        output = json.loads(captured.out)
                        assert output == expected_result
                        mock_close.assert_called_once()
