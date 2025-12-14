"""HTTP API schema conformance tests.

Tests that verify the HTTP API at /api/call endpoint follows the expected
JSON-RPC style request/response schemas used by hook scripts.

This test file addresses R5-C from recommendations-r5-r8.md and helps prevent
bugs like BUG-033 where configuration mismatches between hooks and server
caused integration failures.

Reference: planning_docs/tickets/recommendations-r5-r8.md (R5-C)
"""

from typing import Any
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

from clams.server.http import HttpServer

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_tool_registry() -> dict[str, Any]:
    """Create a mock tool registry with test tools.

    Returns a registry with tools that mimic real MCP tool behavior:
    - ping: Simple tool with no arguments
    - echo: Tool that echoes arguments back
    - store_memory: Tool with required arguments
    - search: Tool returning list results
    """

    async def mock_ping() -> dict[str, str]:
        """Simple health check tool."""
        return {"status": "ok"}

    async def mock_echo(**kwargs: Any) -> dict[str, Any]:
        """Echo back received arguments."""
        return {"echoed": kwargs}

    async def mock_store_memory(
        content: str,
        category: str,
        importance: float = 0.5,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Store memory tool with required and optional args."""
        return {
            "memory_id": "test-123",
            "content": content,
            "category": category,
            "importance": importance,
            "tags": tags or [],
        }

    async def mock_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search tool returning list results."""
        return [{"id": "1", "content": f"Match for: {query}", "score": 0.95}]

    async def mock_error_tool() -> None:
        """Tool that raises an error."""
        raise ValueError("Intentional test error")

    return {
        "ping": mock_ping,
        "echo": mock_echo,
        "store_memory": mock_store_memory,
        "search": mock_search,
        "error_tool": mock_error_tool,
    }


@pytest.fixture
def http_client(mock_tool_registry: dict[str, Any]) -> TestClient:
    """Create a test client for the HTTP server.

    This fixture creates an HttpServer instance with mock services
    and returns a Starlette TestClient for making HTTP requests.
    """
    http_server = HttpServer(
        server=MagicMock(),
        services=MagicMock(),
        tool_registry=mock_tool_registry,
        host="127.0.0.1",
        port=6335,
    )
    app = http_server.create_app()
    return TestClient(app)


# =============================================================================
# Request Schema Tests
# =============================================================================


class TestRequestSchema:
    """Tests for /api/call request schema validation.

    Expected request format (from hooks):
    {
        "method": "tools/call",
        "params": {
            "name": "<tool_name>",
            "arguments": {...}
        }
    }
    """

    def test_valid_request_schema(self, http_client: TestClient) -> None:
        """Valid JSON-RPC style request should succeed."""
        response = http_client.post(
            "/api/call",
            json={
                "method": "tools/call",
                "params": {"name": "ping", "arguments": {}},
            },
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_request_with_arguments(self, http_client: TestClient) -> None:
        """Request with tool arguments should pass them correctly."""
        response = http_client.post(
            "/api/call",
            json={
                "method": "tools/call",
                "params": {
                    "name": "store_memory",
                    "arguments": {
                        "content": "Test content",
                        "category": "fact",
                        "importance": 0.8,
                        "tags": ["test", "schema"],
                    },
                },
            },
        )

        assert response.status_code == 200
        result = response.json()
        assert result["memory_id"] == "test-123"
        assert result["content"] == "Test content"
        assert result["category"] == "fact"
        assert result["importance"] == 0.8
        assert result["tags"] == ["test", "schema"]

    def test_request_with_default_arguments(self, http_client: TestClient) -> None:
        """Request with only required arguments should use defaults."""
        response = http_client.post(
            "/api/call",
            json={
                "method": "tools/call",
                "params": {
                    "name": "store_memory",
                    "arguments": {"content": "Test content", "category": "fact"},
                },
            },
        )

        assert response.status_code == 200
        result = response.json()
        assert result["importance"] == 0.5  # Default value
        assert result["tags"] == []  # Default value

    def test_missing_params_field(self, http_client: TestClient) -> None:
        """Request without params field should return 400."""
        response = http_client.post(
            "/api/call",
            json={"method": "tools/call"},
        )

        assert response.status_code == 400
        assert "error" in response.json()
        assert "Missing tool name" in response.json()["error"]

    def test_missing_name_in_params(self, http_client: TestClient) -> None:
        """Request without name in params should return 400."""
        response = http_client.post(
            "/api/call",
            json={"method": "tools/call", "params": {"arguments": {}}},
        )

        assert response.status_code == 400
        assert "error" in response.json()
        assert "Missing tool name" in response.json()["error"]

    def test_empty_params(self, http_client: TestClient) -> None:
        """Request with empty params should return 400."""
        response = http_client.post(
            "/api/call",
            json={"method": "tools/call", "params": {}},
        )

        assert response.status_code == 400
        assert "Missing tool name" in response.json()["error"]

    def test_null_tool_name(self, http_client: TestClient) -> None:
        """Request with null tool name should return 400."""
        response = http_client.post(
            "/api/call",
            json={"method": "tools/call", "params": {"name": None, "arguments": {}}},
        )

        assert response.status_code == 400
        assert "Missing tool name" in response.json()["error"]

    def test_arguments_optional_when_tool_has_no_params(
        self, http_client: TestClient
    ) -> None:
        """Arguments field should be optional for tools without parameters."""
        response = http_client.post(
            "/api/call",
            json={"method": "tools/call", "params": {"name": "ping"}},
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_method_field_ignored(self, http_client: TestClient) -> None:
        """Method field is documented but not validated - any value works."""
        # The server doesn't validate the 'method' field - it only looks at params
        response = http_client.post(
            "/api/call",
            json={
                "method": "anything",
                "params": {"name": "ping", "arguments": {}},
            },
        )

        assert response.status_code == 200

    def test_extra_fields_ignored(self, http_client: TestClient) -> None:
        """Extra fields in request should be ignored (forward compatibility)."""
        response = http_client.post(
            "/api/call",
            json={
                "method": "tools/call",
                "params": {"name": "ping", "arguments": {}},
                "id": 1,  # JSON-RPC id field
                "jsonrpc": "2.0",  # JSON-RPC version
                "extra_field": "ignored",
            },
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# =============================================================================
# Response Schema Tests - Success Cases
# =============================================================================


class TestSuccessResponseSchema:
    """Tests for /api/call success response schema.

    Success responses can have different shapes:
    - Dict results returned directly: {...}
    - List results returned directly: [...]
    - String results wrapped: {"result": "..."}
    """

    def test_dict_response_returned_directly(self, http_client: TestClient) -> None:
        """Dict tool results should be returned directly."""
        response = http_client.post(
            "/api/call",
            json={"method": "tools/call", "params": {"name": "ping", "arguments": {}}},
        )

        assert response.status_code == 200
        result = response.json()
        # Dict returned directly
        assert isinstance(result, dict)
        assert result == {"status": "ok"}

    def test_list_response_returned_directly(self, http_client: TestClient) -> None:
        """List tool results should be returned directly."""
        response = http_client.post(
            "/api/call",
            json={
                "method": "tools/call",
                "params": {"name": "search", "arguments": {"query": "test"}},
            },
        )

        assert response.status_code == 200
        result = response.json()
        # List returned directly
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["content"] == "Match for: test"

    def test_complex_nested_response(self, http_client: TestClient) -> None:
        """Complex nested structures should be preserved in response."""
        response = http_client.post(
            "/api/call",
            json={
                "method": "tools/call",
                "params": {
                    "name": "echo",
                    "arguments": {
                        "nested": {"level1": {"level2": {"value": 42}}},
                        "array": [1, 2, {"three": 3}],
                    },
                },
            },
        )

        assert response.status_code == 200
        result = response.json()
        assert result["echoed"]["nested"]["level1"]["level2"]["value"] == 42
        assert result["echoed"]["array"] == [1, 2, {"three": 3}]

    def test_response_content_type_is_json(self, http_client: TestClient) -> None:
        """Success responses should have application/json content type."""
        response = http_client.post(
            "/api/call",
            json={"method": "tools/call", "params": {"name": "ping", "arguments": {}}},
        )

        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")


# =============================================================================
# Response Schema Tests - Error Cases
# =============================================================================


class TestErrorResponseSchema:
    """Tests for /api/call error response schema.

    Error responses should have format:
    {
        "error": "error message"
    }
    """

    def test_invalid_json_error_format(self, http_client: TestClient) -> None:
        """Invalid JSON should return error in standard format."""
        response = http_client.post(
            "/api/call",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400
        result = response.json()
        assert "error" in result
        assert "Invalid JSON" in result["error"]

    def test_unknown_tool_error_format(self, http_client: TestClient) -> None:
        """Unknown tool should return 404 with error format."""
        response = http_client.post(
            "/api/call",
            json={
                "method": "tools/call",
                "params": {"name": "nonexistent_tool", "arguments": {}},
            },
        )

        assert response.status_code == 404
        result = response.json()
        assert "error" in result
        assert "Unknown tool" in result["error"]
        assert "nonexistent_tool" in result["error"]

    def test_invalid_arguments_error_format(self, http_client: TestClient) -> None:
        """Invalid arguments should return 400 with error format."""
        response = http_client.post(
            "/api/call",
            json={
                "method": "tools/call",
                "params": {
                    "name": "store_memory",
                    "arguments": {
                        # Missing required 'content' and 'category' arguments
                    },
                },
            },
        )

        assert response.status_code == 400
        result = response.json()
        assert "error" in result
        assert "Invalid arguments" in result["error"]

    def test_tool_error_format(self, http_client: TestClient) -> None:
        """Tool execution error should return 500 with error format."""
        response = http_client.post(
            "/api/call",
            json={
                "method": "tools/call",
                "params": {"name": "error_tool", "arguments": {}},
            },
        )

        assert response.status_code == 500
        result = response.json()
        assert "error" in result
        assert "Tool error" in result["error"]

    def test_error_response_content_type(self, http_client: TestClient) -> None:
        """Error responses should have application/json content type."""
        response = http_client.post(
            "/api/call",
            json={
                "method": "tools/call",
                "params": {"name": "nonexistent_tool", "arguments": {}},
            },
        )

        assert response.status_code == 404
        assert "application/json" in response.headers.get("content-type", "")


# =============================================================================
# JSON-RPC Style Compatibility Tests
# =============================================================================


class TestJsonRpcStyleFormat:
    """Tests verifying JSON-RPC style request format compatibility.

    The API uses a JSON-RPC inspired format but is not fully JSON-RPC 2.0
    compliant. These tests document the actual behavior and expected format.
    """

    def test_standard_hook_request_format(self, http_client: TestClient) -> None:
        """Request format used by hooks should work correctly.

        This is the exact format hooks use (from session_start.sh):
        request=$(jq -n --arg name "$tool_name" --argjson args "$args" \
            '{method: "tools/call", params: {name: $name, arguments: $args}}')
        """
        response = http_client.post(
            "/api/call",
            json={
                "method": "tools/call",
                "params": {"name": "ping", "arguments": {}},
            },
        )

        assert response.status_code == 200

    def test_mcp_call_tool_format(self, http_client: TestClient) -> None:
        """MCP-style tools/call method should work."""
        response = http_client.post(
            "/api/call",
            json={
                "method": "tools/call",
                "params": {
                    "name": "echo",
                    "arguments": {"message": "hello"},
                },
            },
        )

        assert response.status_code == 200
        assert response.json()["echoed"]["message"] == "hello"

    def test_params_name_must_be_string(self, http_client: TestClient) -> None:
        """Tool name must be a string."""
        response = http_client.post(
            "/api/call",
            json={
                "method": "tools/call",
                "params": {"name": 123, "arguments": {}},
            },
        )

        # Numeric tool name becomes string key lookup which fails
        assert response.status_code == 404

    def test_arguments_must_be_dict_like(self, http_client: TestClient) -> None:
        """Arguments must be a dict (or dict-like) for **kwargs unpacking."""
        response = http_client.post(
            "/api/call",
            json={
                "method": "tools/call",
                "params": {"name": "echo", "arguments": ["not", "a", "dict"]},
            },
        )

        # List can't be unpacked as **kwargs
        assert response.status_code == 400
        assert "Invalid arguments" in response.json()["error"]


# =============================================================================
# Malformed Request Tests
# =============================================================================


class TestMalformedRequests:
    """Tests for handling malformed requests gracefully."""

    def test_empty_body(self, http_client: TestClient) -> None:
        """Empty request body should return 400."""
        response = http_client.post(
            "/api/call",
            content="",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400
        assert "error" in response.json()

    @pytest.mark.xfail(
        reason="Server doesn't handle null JSON body gracefully - crashes with AttributeError",
        strict=True,
    )
    def test_null_body(self, http_client: TestClient) -> None:
        """Null JSON body should return 400.

        NOTE: This test currently fails because the server tries to call
        body.get() on None. This is a potential bug to fix in http.py.
        """
        response = http_client.post(
            "/api/call",
            content="null",
            headers={"Content-Type": "application/json"},
        )

        # null body means params = None, which should trigger missing tool name
        assert response.status_code == 400
        assert "error" in response.json()

    @pytest.mark.xfail(
        reason="Server doesn't handle array JSON body gracefully - crashes with AttributeError",
        strict=True,
    )
    def test_array_body(self, http_client: TestClient) -> None:
        """Array JSON body should return 400 (not supported).

        NOTE: This test currently fails because the server tries to call
        body.get() on a list. This is a potential bug to fix in http.py.
        """
        response = http_client.post(
            "/api/call",
            json=[{"method": "tools/call", "params": {"name": "ping"}}],
        )

        # Array body doesn't have .get() method, should fail gracefully
        assert response.status_code == 400

    def test_truncated_json(self, http_client: TestClient) -> None:
        """Truncated JSON should return 400 with clear error."""
        response = http_client.post(
            "/api/call",
            content='{"method": "tools/call", "params":',
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["error"]

    def test_wrong_content_type_with_valid_json(self, http_client: TestClient) -> None:
        """Request with wrong content type but valid JSON body."""
        response = http_client.post(
            "/api/call",
            content='{"method": "tools/call", "params": {"name": "ping"}}',
            headers={"Content-Type": "text/plain"},
        )

        # Starlette/uvicorn may still parse JSON despite content-type
        # Behavior here is implementation-dependent
        # Important: don't crash, return either success or clear error
        assert response.status_code in (200, 400, 415)

    def test_unicode_in_arguments(self, http_client: TestClient) -> None:
        """Unicode content in arguments should be handled correctly."""
        # Use actual unicode characters (wave emoji + Chinese characters)
        unicode_message = "Hello \U0001f44b \u4e16\u754c"  # Hello wave-emoji world
        response = http_client.post(
            "/api/call",
            json={
                "method": "tools/call",
                "params": {
                    "name": "echo",
                    "arguments": {"message": unicode_message},
                },
            },
        )

        assert response.status_code == 200
        result = response.json()
        assert result["echoed"]["message"] == unicode_message

    def test_very_large_arguments(self, http_client: TestClient) -> None:
        """Large argument values should be handled without crashing."""
        large_content = "x" * 100000  # 100KB of content
        response = http_client.post(
            "/api/call",
            json={
                "method": "tools/call",
                "params": {"name": "echo", "arguments": {"large": large_content}},
            },
        )

        assert response.status_code == 200
        result = response.json()
        assert len(result["echoed"]["large"]) == 100000


# =============================================================================
# HTTP Status Code Tests
# =============================================================================


class TestHttpStatusCodes:
    """Tests verifying correct HTTP status codes for various scenarios."""

    def test_success_returns_200(self, http_client: TestClient) -> None:
        """Successful tool call returns 200."""
        response = http_client.post(
            "/api/call",
            json={"method": "tools/call", "params": {"name": "ping", "arguments": {}}},
        )
        assert response.status_code == 200

    def test_missing_params_returns_400(self, http_client: TestClient) -> None:
        """Missing params returns 400 Bad Request."""
        response = http_client.post("/api/call", json={"method": "tools/call"})
        assert response.status_code == 400

    def test_invalid_json_returns_400(self, http_client: TestClient) -> None:
        """Invalid JSON returns 400 Bad Request."""
        response = http_client.post(
            "/api/call",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400

    def test_unknown_tool_returns_404(self, http_client: TestClient) -> None:
        """Unknown tool returns 404 Not Found."""
        response = http_client.post(
            "/api/call",
            json={
                "method": "tools/call",
                "params": {"name": "unknown", "arguments": {}},
            },
        )
        assert response.status_code == 404

    def test_invalid_arguments_returns_400(self, http_client: TestClient) -> None:
        """Invalid arguments returns 400 Bad Request."""
        response = http_client.post(
            "/api/call",
            json={
                "method": "tools/call",
                "params": {"name": "store_memory", "arguments": {}},
            },
        )
        assert response.status_code == 400

    def test_tool_error_returns_500(self, http_client: TestClient) -> None:
        """Tool execution error returns 500 Internal Server Error."""
        response = http_client.post(
            "/api/call",
            json={
                "method": "tools/call",
                "params": {"name": "error_tool", "arguments": {}},
            },
        )
        assert response.status_code == 500

    def test_get_method_not_allowed(self, http_client: TestClient) -> None:
        """GET request to /api/call should return 405."""
        response = http_client.get("/api/call")
        assert response.status_code == 405
