"""Regression tests for BUG-076: MCP client does not reconnect after server restart.

Verifies that the CALM server uses Streamable HTTP transport instead of the
deprecated SSE transport. The Streamable HTTP transport provides:
- Session management via Mcp-Session-Id headers
- Built-in reconnection support in the MCP client
- Proper session lifecycle (POST for tool calls, GET for SSE stream, DELETE for cleanup)

These tests verify the server-side transport migration without starting a full
HTTP server -- they test the ASGI app construction and routing directly.
"""

from __future__ import annotations

from typing import Any


class TestStreamableHTTPTransportUsed:
    """Verify the server uses StreamableHTTPSessionManager, not SseServerTransport."""

    def test_main_does_not_import_sse_transport(self) -> None:
        """The server main module must not reference SseServerTransport."""
        import inspect

        from calm.server import main

        source = inspect.getsource(main)
        assert "SseServerTransport" not in source, (
            "main.py still references SseServerTransport. "
            "BUG-076 requires migration to StreamableHTTPSessionManager."
        )

    def test_main_imports_streamable_http_manager(self) -> None:
        """The server main module must reference StreamableHTTPSessionManager."""
        import inspect

        from calm.server import main

        source = inspect.getsource(main)
        assert "StreamableHTTPSessionManager" in source, (
            "main.py does not reference StreamableHTTPSessionManager. "
            "BUG-076 requires migration to Streamable HTTP transport."
        )

    def test_main_does_not_use_sse_endpoint(self) -> None:
        """The server must not route to /sse endpoint."""
        import inspect

        from calm.server import main

        source = inspect.getsource(main)
        # Check that /sse endpoint routing is removed
        assert 'path == "/sse"' not in source, (
            "main.py still routes to /sse endpoint. "
            "BUG-076 requires migration to /mcp endpoint."
        )

    def test_main_uses_mcp_endpoint(self) -> None:
        """The server must route to /mcp endpoint."""
        import inspect

        from calm.server import main

        source = inspect.getsource(main)
        assert '"/mcp"' in source, (
            "main.py does not route to /mcp endpoint. "
            "BUG-076 requires the Streamable HTTP endpoint at /mcp."
        )


class TestConfigMergeUsesHTTPTransport:
    """Verify config_merge registers the server with HTTP transport type."""

    def test_merge_mcp_server_uses_http_type(self) -> None:
        """merge_mcp_server must produce type=http, not type=sse."""
        from calm.install.config_merge import merge_mcp_server

        result = merge_mcp_server({}, "http://127.0.0.1:6335/mcp")
        calm_entry = result["mcpServers"]["calm"]
        assert calm_entry["type"] == "http", (
            f"Expected type='http' for Streamable HTTP transport, "
            f"got type='{calm_entry['type']}'"
        )

    def test_merge_mcp_server_uses_mcp_path(self) -> None:
        """merge_mcp_server must use /mcp path, not /sse."""
        from calm.install.config_merge import merge_mcp_server

        result = merge_mcp_server({}, "http://127.0.0.1:6335/mcp")
        calm_entry = result["mcpServers"]["calm"]
        assert calm_entry["url"].endswith("/mcp"), (
            f"Expected URL ending with /mcp, got '{calm_entry['url']}'"
        )
        assert "/sse" not in calm_entry["url"], (
            f"URL must not contain /sse path, got '{calm_entry['url']}'"
        )

    def test_register_mcp_server_writes_http_config(self, tmp_path: Any) -> None:
        """register_mcp_server must write Streamable HTTP config to disk."""
        import json

        from calm.install.config_merge import register_mcp_server

        config_path = tmp_path / ".claude.json"
        register_mcp_server(config_path)

        config = json.loads(config_path.read_text())
        calm_entry = config["mcpServers"]["calm"]
        assert calm_entry["type"] == "http"
        assert calm_entry["url"].endswith("/mcp")
        assert "command" not in calm_entry
        assert "args" not in calm_entry

    def test_register_mcp_server_upgrades_from_sse(self, tmp_path: Any) -> None:
        """register_mcp_server must upgrade an existing SSE config to HTTP."""
        import json

        from calm.install.config_merge import register_mcp_server

        config_path = tmp_path / ".claude.json"
        # Write old SSE config
        old_config = {
            "mcpServers": {
                "calm": {
                    "type": "sse",
                    "url": "http://127.0.0.1:6335/sse",
                }
            }
        }
        config_path.write_text(json.dumps(old_config))

        # Re-register -- should overwrite with HTTP
        register_mcp_server(config_path)

        config = json.loads(config_path.read_text())
        calm_entry = config["mcpServers"]["calm"]
        assert calm_entry["type"] == "http", (
            "register_mcp_server did not upgrade SSE config to HTTP"
        )
        assert calm_entry["url"].endswith("/mcp"), (
            "register_mcp_server did not change /sse URL to /mcp"
        )


class TestStreamableHTTPSessionManager:
    """Test that the session manager is correctly wired in the server."""

    def test_session_manager_initialized_with_app_kwarg(self) -> None:
        """StreamableHTTPSessionManager must be constructed with app= kwarg."""
        import ast
        import inspect

        from calm.server import main

        source = inspect.getsource(main._run_server_async)
        tree = ast.parse(source)

        # Find the StreamableHTTPSessionManager(...) call
        found_call = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "StreamableHTTPSessionManager":
                    found_call = True
                    # Check it's called with app= keyword
                    kwarg_names = [kw.arg for kw in node.keywords]
                    assert "app" in kwarg_names, (
                        "StreamableHTTPSessionManager must be called with app= kwarg "
                        "passing the MCP server instance"
                    )
                    break

        assert found_call, (
            "No call to StreamableHTTPSessionManager() found in _run_server_async"
        )

    def test_session_manager_run_used_in_lifespan(self) -> None:
        """The session manager's run() must be used as a lifespan context manager."""
        import inspect

        from calm.server import main

        source = inspect.getsource(main._run_server_async)
        assert "session_manager.run()" in source, (
            "_run_server_async must call session_manager.run() in a lifespan "
            "context manager for proper lifecycle management"
        )


class TestServerAllowsDeleteMethod:
    """Verify CORS allows DELETE method for session termination."""

    def test_cors_allows_delete_method(self) -> None:
        """CORS middleware must allow DELETE for Streamable HTTP session cleanup."""
        import inspect

        from calm.server import main

        source = inspect.getsource(main)
        assert "DELETE" in source, (
            "CORS middleware must allow DELETE method for "
            "Streamable HTTP session termination"
        )
